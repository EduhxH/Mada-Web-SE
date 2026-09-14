"""As duas rotinas de manutencao, num sitio so: material novo e horario.

Existiam duas vezes, e por isso esta aqui. A linha de comandos tinha-as dentro
de `comando_verificar_moodle` e `comando_horario`, a medir em `print`s; o painel
de administracao precisava do mesmo trabalho para o botao "verificar agora".
Copiar era garantir que as duas versoes se afastavam - e a parte delicada nao e
o pedido HTTP, e a contabilidade a seguir: descarregar so o que e novo, marcar
como examinado o que nao deu ficheiro, e registar nas novidades apenas o que
produziu algo.

Cada rotina devolve um resultado estruturado e fala pelo caminho por um
`ao_dizer` opcional. Quem chama decide o que fazer com a voz: a linha de
comandos passa `print`, o painel passa o registo do servidor e ve a operacao a
correr ao vivo. O resumo final fica com quem chama, porque a consola e o painel
querem formatos diferentes da mesma verdade.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.crawler import horarios, moodle
from app.indexing import atualizacao
from app.models import novidades

RAIZ_MOODLE = Path("data") / "raw" / "psi9"

Voz = Callable[[str], None]


def _calado(_texto: str) -> None:
    pass


@dataclass
class Conteudos:
    """O que a verificacao do Moodle encontrou e trouxe."""

    vistos: int = 0
    novos: list = field(default_factory=list)
    ficheiros: int = 0
    bytes_totais: int = 0
    esteris: int = 0
    registadas: int = 0
    erro: str = ""
    segundos: float = 0.0

    @property
    def falhou(self) -> bool:
        return bool(self.erro)

    @property
    def houve_novidade(self) -> bool:
        return self.ficheiros > 0

    def resumo(self) -> str:
        if self.erro:
            return self.erro
        if not self.novos:
            return f"{self.vistos} módulos verificados, nada de novo"
        return (
            f"{self.vistos} módulos verificados, {len(self.novos)} novidade(s),"
            f" {self.ficheiros} ficheiro(s)"
        )


@dataclass
class Horario:
    verificou: bool = False
    mudou: bool = False
    motivo: str = ""
    bytes_guardados: int = 0
    erro: str = ""
    segundos: float = 0.0

    @property
    def falhou(self) -> bool:
        return bool(self.erro)

    def resumo(self) -> str:
        return self.erro or self.motivo or "nada a fazer"


def verificar_conteudos(
    disciplinas: list[str] | None = None,
    intervalo: float = 1.0,
    raiz: Path | None = None,
    ao_dizer: Voz = _calado,
) -> Conteudos:
    """Procura material novo no Moodle e descarrega so esse.

    Um pedido por disciplina em vez das centenas de uma sincronizacao completa,
    para poder correr tres vezes por dia sem incomodar o servidor da escola.
    """
    raiz = raiz or RAIZ_MOODLE
    inicio = time.perf_counter()
    resultado = Conteudos()

    ao_dizer("A procurar material novo no Moodle...")
    try:
        resultado.novos, resultado.vistos = moodle.verificar(
            raiz, disciplinas, intervalo
        )
    except moodle.ErroMoodle as erro:
        resultado.erro = str(erro)
        resultado.segundos = time.perf_counter() - inicio
        return resultado
    except Exception as erro:
        resultado.erro = f"falhou a verificação: {erro}"
        resultado.segundos = time.perf_counter() - inicio
        return resultado

    ao_dizer(f"{resultado.vistos} módulos verificados.")
    if not resultado.novos:
        resultado.segundos = time.perf_counter() - inicio
        ao_dizer("Nada de novo.")
        return resultado

    for item in resultado.novos:
        ao_dizer(f"  novo: [{item.disciplina}] {item.titulo}")

    ao_dizer(f"A descarregar {len(resultado.novos)} módulo(s)...")
    antes = moodle.modulos_com_ficheiros(raiz)
    identificadores = {item.identificador for item in resultado.novos}
    try:
        relatorio = moodle.sincronizar(
            raiz,
            disciplinas_pedidas=disciplinas,
            intervalo=intervalo,
            apenas=identificadores,
        )
    except Exception as erro:
        resultado.erro = f"falhou o descarregamento: {erro}"
        resultado.segundos = time.perf_counter() - inicio
        return resultado

    resultado.ficheiros = relatorio.ficheiros
    resultado.bytes_totais = relatorio.bytes_totais

    # Marcar tudo o que foi examinado, mesmo o que nao deu ficheiro: senao uma
    # pasta vazia e anunciada como novidade todos os dias. Dos 305 modulos deste
    # Moodle so 69 alguma vez deram ficheiro - sem este registo eram 236 falsas
    # novidades por dia. A sincronizacao completa volta a tentar tudo, por isso
    # nada fica perdido.
    moodle.marcar_vistos(raiz, identificadores)

    produziram = moodle.modulos_com_ficheiros(raiz) - antes
    resultado.esteris = len(resultado.novos) - len(produziram)
    resultado.registadas = novidades.registar(
        [
            (item.disciplina, item.titulo, item.url)
            for item in resultado.novos
            if item.identificador in produziram
        ]
    )
    resultado.segundos = time.perf_counter() - inicio
    mb = resultado.bytes_totais / 1024 / 1024
    ao_dizer(f"{resultado.ficheiros} ficheiro(s), {mb:.1f} MB.")
    if resultado.esteris:
        ao_dizer(
            f"{resultado.esteris} sem ficheiro"
            " (pasta vazia ou formato que não lemos)."
        )
    return resultado


def vigiar_horario(
    momento: datetime | None = None,
    forcar: bool = False,
    ao_dizer: Voz = _calado,
) -> Horario:
    """Ve se saiu horario novo, e descarrega se saiu.

    A decisao de valer a pena verificar e do `horarios`, nao daqui: a regra
    (quinta e sexta a partir do meio-dia, fim de semana a qualquer hora, e
    calado depois de apanhar o da semana) esta testada la.
    """
    agora = momento or datetime.now()
    inicio = time.perf_counter()
    estado = horarios.ler_estado()

    if not forcar:
        vale, motivo = horarios.deve_verificar(agora, estado)
        if not vale:
            ao_dizer(f"Nada a fazer: {motivo}.")
            return Horario(
                motivo=f"nada a fazer: {motivo}",
                segundos=time.perf_counter() - inicio,
            )

    ao_dizer("A entrar no Moodle...")
    try:
        url_base, utilizador, senha = moodle.configuracao()
        sessao = moodle.iniciar_sessao(url_base, utilizador, senha)
    except moodle.ErroMoodle as erro:
        return Horario(erro=str(erro), segundos=time.perf_counter() - inicio)
    except Exception as erro:
        return Horario(
            erro=f"falhou a entrada no Moodle: {erro}",
            segundos=time.perf_counter() - inicio,
        )

    try:
        obtido = horarios.verificar(sessao, url_base, agora, forcar=forcar)
    except Exception as erro:
        return Horario(
            erro=f"falhou a verificação do horário: {erro}",
            segundos=time.perf_counter() - inicio,
        )

    ao_dizer(obtido.motivo.capitalize() + ".")
    if obtido.mudou:
        mb = obtido.bytes_guardados / 1024 / 1024
        ao_dizer(f"Guardado em {horarios.PASTA} ({mb:.1f} MB).")
    return Horario(
        verificou=obtido.verificou,
        mudou=obtido.mudou,
        motivo=obtido.motivo,
        bytes_guardados=obtido.bytes_guardados,
        segundos=time.perf_counter() - inicio,
    )


def reindexar(ao_dizer: Voz = _calado):
    """Reconstroi o indice a partir do que esta em disco.

    Devolve `(alteracoes, relatorio, termos)`, como `atualizacao.reindexar`. Sao
    dois minutos de trabalho, por isso quem chama deve ter confirmado antes que
    ha razao para os gastar.
    """
    ao_dizer("A reindexar o corpus...")
    alteracoes, relatorio, termos = atualizacao.reindexar()
    total = alteracoes.mantidos + len(alteracoes.novos) + len(alteracoes.alterados)
    ao_dizer(f"{total} documentos, {termos} termos únicos. {alteracoes.resumo()}")
    return alteracoes, relatorio, termos
