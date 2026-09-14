"""Os pontos por cima dos menus do painel: "ha coisa nova aqui desde a ultima vez".

Um contador sem memoria do que ja foi visto nao e um aviso, e um numero. O que
faz disto util e guardar a marca de quando cada secao foi aberta e contar so o
que veio depois - abrir a secao apaga o ponto, exactamente como se espera.

As marcas vivem num JSON de tres linhas. Nao vao para a base de dados de uso
porque nao dizem nada sobre a turma: dizem quando e que **eu** olhei para o
painel, o que e preferencia de interface e nao dado de utilizacao.

Cada secao tem a sua unidade de medida, e e isso que decide o que o ponto conta:

    visao          buscas novas          (o motor foi usado desde que olhei)
    utilizadores   entradas novas        (alguem entrou desde que olhei)
    registo        avisos e erros novos  (algo correu mal desde que olhei)
    automatizacao  a ultima corrida falhou

A marca guardada e sempre um **numero de sequencia**, nunca um carimbo de tempo:
o numero do ultimo evento de uso, ou o da ultima linha de registo. Com carimbos
ao segundo, uma busca feita no mesmo segundo em que se abriu o painel ficava
para sempre por contar - e isso e o tipo de erro que nunca se ve acontecer.
"""

import json
from pathlib import Path

from app.analytics import uso
from app.interface import operacoes, registo as registo_servidor

CAMINHO = Path("data") / "painel-visto.json"

VISAO = "visao"
UTILIZADORES = "utilizadores"
REGISTO = "registo"
AUTOMATIZACAO = "automatizacao"

# Um ponto com "247" nao diz mais do que um ponto com "9+": acima disto o numero
# deixa de ser informacao e passa a ser largura.
MAXIMO_MOSTRADO = 9


def _ler() -> dict:
    if not CAMINHO.exists():
        return {}
    try:
        dados = json.loads(CAMINHO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _escrever(marcas: dict) -> None:
    try:
        CAMINHO.parent.mkdir(parents=True, exist_ok=True)
        CAMINHO.write_text(
            json.dumps(marcas, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError:
        # Nao poder guardar a marca faz o ponto reaparecer, o que e chato e nada
        # mais. Nao e motivo para o painel deixar de abrir.
        pass


def marcar_visto(seccao: str, conexao=None) -> None:
    """Chamada quando a secao e aberta. Zera o ponto dessa secao.

    A marca e sempre um numero de sequencia - o do registo do servidor, ou o do
    ultimo evento de uso - e nunca um carimbo de tempo. Com carimbos ao segundo,
    uma busca feita no mesmo segundo em que se abriu o painel ficava para sempre
    por contar.
    """
    marcas = _ler()
    if seccao == REGISTO:
        marcas[REGISTO] = {"seq": registo_servidor.ultimo_seq()}
    elif seccao in (VISAO, UTILIZADORES) and conexao is not None:
        try:
            marcas[seccao] = {"evento": uso.ultimo_id(conexao)}
        except Exception:
            return
    else:
        marcas[seccao] = {"visto": True}
    _escrever(marcas)


def contar(conexao) -> dict[str, int]:
    """Quantas coisas novas ha em cada secao. Nunca levanta.

    O painel inteiro depende disto para se desenhar, e uma base de dados
    momentaneamente trancada nao pode ser motivo para nao abrir - sem avisos o
    painel continua a servir para tudo o resto.
    """
    marcas = _ler()
    contas = {VISAO: 0, UTILIZADORES: 0, REGISTO: 0, AUTOMATIZACAO: 0}

    seq_visto = int(marcas.get(REGISTO, {}).get("seq", 0) or 0)
    contas[REGISTO] = registo_servidor.contar_desde(seq_visto)

    # Sem marca, o painel abre limpo: a primeira visita nao mostra tudo o que ja
    # aconteceu como se fosse novidade. A marca e escrita ao abrir.
    for seccao, tipo in (
        (VISAO, uso.EVENTO_BUSCA),
        (UTILIZADORES, uso.EVENTO_ENTRADA),
    ):
        marca = marcas.get(seccao, {}).get("evento")
        if marca is None:
            continue
        try:
            contas[seccao] = uso.contar_depois_de(conexao, tipo, int(marca))
        except Exception:
            contas[seccao] = 0

    for estado in operacoes.todos().values():
        if estado["bem"] is False:
            contas[AUTOMATIZACAO] += 1

    return contas


def etiqueta(quantos: int) -> str:
    """O texto do ponto: "" quando nao ha, "9+" quando ha muitos."""
    if quantos <= 0:
        return ""
    if quantos > MAXIMO_MOSTRADO:
        return f"{MAXIMO_MOSTRADO}+"
    return str(quantos)
