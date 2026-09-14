"""As operacoes manuais do painel: verificar conteudos, verificar horario.

O agendador ja faz isto tres vezes por dia. Isto e para quando nao se quer
esperar: um professor publica a ficha no meio da aula e o botao traz o material
sem ir a linha de comandos.

Tres decisoes que fazem a diferenca entre um botao e um botao utilizavel:

**Corre num fio separado.** Verificar sao catorze segundos; se houver material
novo, mais o descarregamento e dois minutos de reindexacao. Um pedido HTTP que
segurasse isso ficaria pendurado, o browser desistia a meio e ninguem saberia se
a operacao tinha corrido. O pedido devolve "comecou" e o painel pergunta depois
como vai.

**Uma de cada vez.** Duas verificacoes em paralelo entrariam duas vezes no
Moodle e reindexariam o mesmo corpus ao mesmo tempo, com as duas a escrever no
mesmo ficheiro SQLite. A tranca e por isso, e o botao fica desativado enquanto
houver uma a correr.

**Fala para o registo do servidor.** A rotina comunica por `print`; o `Canal` do
registo encaminha isso, e o painel mostra as mesmas linhas ao vivo na consola e
no historico. Se falhar, o motivo fica escrito - que era precisamente o que
faltava quando isto so existia como tarefa agendada.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime

from app.interface import registo

# As chaves que o painel usa nos botoes e nos pedidos.
CONTEUDOS = "conteudos"
HORARIO = "horario"
NOMES = {
    CONTEUDOS: "Verificar conteúdos novos",
    HORARIO: "Verificar horário",
}

# Uma verificacao com reindexacao anda pelos dois minutos e meio. Acima de dez
# minutos alguma coisa esta pendurada, e vale mais dizer isso do que deixar o
# painel a mostrar "a correr" para sempre.
SEGUNDOS_LIMITE = 600


@dataclass
class Estado:
    """O que se sabe sobre a ultima vez que esta operacao correu."""

    nome: str
    a_correr: bool = False
    comecou: str = ""
    terminou: str = ""
    segundos: float = 0.0
    bem: bool | None = None
    resumo: str = ""
    desde_seq: int = 0
    # Relogio monotonico do arranque, para medir se a operacao se perdeu. Nao
    # entra no JSON: e detalhe de implementacao, nao informacao para o ecra.
    _inicio: float = 0.0

    def como_json(self) -> dict:
        return {
            "nome": self.nome,
            "rotulo": NOMES.get(self.nome, self.nome),
            "a_correr": self.a_correr,
            "comecou": self.comecou,
            "terminou": self.terminou,
            "segundos": round(self.segundos, 1),
            "bem": self.bem,
            "resumo": self.resumo,
            "desde_seq": self.desde_seq,
        }


_tranca = threading.Lock()
_estados: dict[str, Estado] = {nome: Estado(nome) for nome in NOMES}
_a_correr: str | None = None


def estado(nome: str) -> Estado:
    with _tranca:
        return _estados[nome]


def todos() -> dict[str, dict]:
    with _tranca:
        return {nome: e.como_json() for nome, e in _estados.items()}


def ocupado() -> str | None:
    """O nome da operacao em curso, ou None. Serve para desativar os botoes."""
    with _tranca:
        if _a_correr is None:
            return None
        atual = _estados[_a_correr]
        # Uma operacao que passou do limite deixa de contar como ocupada: sem
        # isto, um pedido pendurado no Moodle bloqueava o painel para sempre e a
        # unica saida era reiniciar o servidor.
        if atual.a_correr and time.monotonic() - atual._inicio > SEGUNDOS_LIMITE:
            return None
        return _a_correr


def iniciar(nome: str) -> tuple[bool, str]:
    """Arranca a operacao num fio. Devolve (comecou?, porque nao).

    Nunca levanta: isto e chamado por um pedido HTTP e um `POST` que estoure
    deixa o administrador sem resposta nenhuma.
    """
    if nome not in NOMES:
        return False, "operação desconhecida"

    with _tranca:
        global _a_correr
        if _a_correr is not None:
            atual = _estados[_a_correr]
            passou = time.monotonic() - atual._inicio
            if atual.a_correr and passou <= SEGUNDOS_LIMITE:
                return False, f"já está a correr: {NOMES[_a_correr]}"
            # Passou do limite: assume-se perdida e deixa-se seguir a nova.
            atual.a_correr = False
            atual.bem = False
            atual.resumo = f"sem resposta depois de {SEGUNDOS_LIMITE}s"
        alvo = _estados[nome]
        alvo.a_correr = True
        alvo.bem = None
        alvo.comecou = datetime.now().isoformat(timespec="seconds")
        alvo.terminou = ""
        alvo.segundos = 0.0
        alvo.resumo = "a correr..."
        alvo.desde_seq = registo.ultimo_seq()
        alvo._inicio = time.monotonic()
        _a_correr = nome

    fio = threading.Thread(
        target=_correr, args=(nome,), name=f"operacao-{nome}", daemon=True
    )
    fio.start()
    return True, ""


def _correr(nome: str) -> None:
    canal = registo.Canal(nome)
    registo.anotar(registo.INFO, f"--- {NOMES[nome]}: a começar ---", nome)
    bem, resumo = False, ""
    inicio = time.monotonic()
    try:
        if nome == CONTEUDOS:
            bem, resumo = _passo_conteudos(canal.write)
        else:
            bem, resumo = _passo_horario(canal.write)
    except Exception as erro:
        registo.excecao(f"{NOMES[nome]} rebentou", nome)
        bem, resumo = False, f"rebentou: {erro}"
    finally:
        canal.flush()
        duracao = time.monotonic() - inicio
        with _tranca:
            global _a_correr
            alvo = _estados[nome]
            alvo.a_correr = False
            alvo.bem = bem
            alvo.resumo = resumo
            alvo.segundos = duracao
            alvo.terminou = datetime.now().isoformat(timespec="seconds")
            if _a_correr == nome:
                _a_correr = None
        nivel = registo.INFO if bem else registo.ERRO
        registo.anotar(
            nivel, f"--- {NOMES[nome]}: {resumo} ({duracao:.0f}s) ---", nome
        )


def _dizer(escrever):
    """Adapta o `write` do canal ao `ao_dizer` da rotina (uma linha de cada vez)."""

    def voz(texto: str) -> None:
        escrever(texto + "\n")

    return voz


def _passo_conteudos(escrever) -> tuple[bool, str]:
    from app.crawler import rotina

    resultado = rotina.verificar_conteudos(ao_dizer=_dizer(escrever))
    if resultado.falhou:
        return False, resultado.erro
    if not resultado.houve_novidade:
        return True, resultado.resumo()

    # Reindexar so quando ha o que indexar: sao dois minutos, e o corpus nao
    # mudou se nao entrou ficheiro nenhum.
    rotina.reindexar(ao_dizer=_dizer(escrever))
    return True, f"{resultado.resumo()}, corpus reindexado"


def _passo_horario(escrever) -> tuple[bool, str]:
    from app.crawler import rotina

    resultado = rotina.vigiar_horario(ao_dizer=_dizer(escrever))
    if resultado.falhou:
        return False, resultado.erro
    if not resultado.mudou:
        return True, resultado.resumo()

    rotina.reindexar(ao_dizer=_dizer(escrever))
    return True, "horário novo, corpus reindexado"


def reiniciar_para_testes() -> None:
    global _a_correr
    with _tranca:
        _a_correr = None
        for nome in NOMES:
            _estados[nome] = Estado(nome)
