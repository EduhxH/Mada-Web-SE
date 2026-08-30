"""Le a intencao escrita na pergunta: disciplina, recencia, tipo.

"ultima ficha da materia de portugues" nao e uma pergunta semantica - e uma
pergunta estruturada vestida de linguagem natural. Pede um filtro
(portugues), uma ordenacao (ultima) e um tipo (ficha). Medido: os embeddings
dao um empate na parte do meio e nada nas outras duas.

Num corpus fechado com onze disciplinas conhecidas, casar nomes e mais fiavel
do que esperar que um modelo geral adivinhe o calao da escola. O que se perde
em elegancia ganha-se em poder inspecionar e corrigir.

O termo reconhecido sai da consulta: se "portugues" ja virou filtro, deixa-lo
tambem como termo de busca puxaria documentos que apenas falam de portugues.
"""

from app.indexing.tokenizer import remover_acentos

# Nomes por que os alunos tratam cada disciplina. Escritos a mao de proposito.
# Sem siglas de uma ou duas letras ("so", "ai", "ef"): apanhavam palavras
# comuns e o filtro errado e pior que filtro nenhum.
ALCUNHAS = {
    "portugues": "Português",
    "matematica": "Matemática",
    "ingles": "Inglês",
    "tic": "TIC",
    "fisica quimica": "Física-Química",
    "fisico quimica": "Física-Química",
    "quimica": "Física-Química",
    "fisica": "Física-Química",
    "educacao fisica": "Educação Física",
    "desporto": "Educação Física",
    "programacao": "Programação e Sistemas de Informação",
    "sistemas de informacao": "Programação e Sistemas de Informação",
    "arquitetura de computadores": "Arquitetura de Computadores",
    "arquitetura": "Arquitetura de Computadores",
    "sistemas operativos": "Sistemas Operativos",
    "area de integracao": "Área de Integração",
}

# Palavras que pedem o mais recente em vez do mais relevante.
MARCAS_DE_RECENCIA = (
    "ultima", "ultimo", "ultimas", "ultimos",
    "mais recente", "mais recentes", "recente",
    "nova", "novo", "novas", "novos",
)

# Ligacoes que sobram quando se retira o nome da disciplina: "ficha de" fica
# a apontar para o vazio.
_LIGACOES = {"de", "da", "do", "das", "dos", "em", "no", "na"}


def _normalizar(texto: str) -> str:
    return remover_acentos((texto or "").lower())


def _sem_pedaco(palavras: list[str], inicio: int, quantas: int) -> list[str]:
    """Tira o pedaco reconhecido e a ligacao que ficou pendurada antes dele."""
    corte_inicial = inicio
    if inicio and palavras[inicio - 1] in _LIGACOES:
        corte_inicial -= 1
    return palavras[:corte_inicial] + palavras[inicio + quantas :]


def detetar_disciplina(
    consulta: str, disponiveis: list[str] | None = None
) -> tuple[str | None, str]:
    """(disciplina, consulta sem o nome dela).

    As alcunhas mais longas sao tentadas primeiro, para "educacao fisica" nao
    ser lida como "fisica".
    """
    palavras = _normalizar(consulta).split()
    if not palavras:
        return None, consulta

    permitidas = set(disponiveis) if disponiveis else None
    ordenadas = sorted(ALCUNHAS.items(), key=lambda par: -len(par[0].split()))

    for alcunha, disciplina in ordenadas:
        if permitidas is not None and disciplina not in permitidas:
            continue
        pedaco = alcunha.split()
        for inicio in range(len(palavras) - len(pedaco) + 1):
            if palavras[inicio : inicio + len(pedaco)] == pedaco:
                resto = _sem_pedaco(palavras, inicio, len(pedaco))
                # Se a disciplina era a pergunta toda, nao ha o que filtrar:
                # devolve-se a consulta original para nao ficar vazia.
                return disciplina, " ".join(resto) if resto else consulta
    return None, consulta


def pede_recente(consulta: str) -> bool:
    normal = _normalizar(consulta)
    palavras = normal.split()
    for marca in MARCAS_DE_RECENCIA:
        pedaco = marca.split()
        for inicio in range(len(palavras) - len(pedaco) + 1):
            if palavras[inicio : inicio + len(pedaco)] == pedaco:
                return True
    return False


def limpar_recencia(consulta: str) -> str:
    """Tira as marcas de recencia: ja viraram ordenacao, nao sao termos."""
    palavras = _normalizar(consulta).split()
    for marca in sorted(MARCAS_DE_RECENCIA, key=lambda m: -len(m.split())):
        pedaco = marca.split()
        inicio = 0
        while inicio <= len(palavras) - len(pedaco):
            if palavras[inicio : inicio + len(pedaco)] == pedaco:
                palavras = _sem_pedaco(palavras, inicio, len(pedaco))
                continue
            inicio += 1
    return " ".join(palavras)
