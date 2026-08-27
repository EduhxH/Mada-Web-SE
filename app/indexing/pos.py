"""Classificacao morfologica leve para portugues, por sufixo.

Nao substitui um etiquetador treinado: e um conjunto de regras conservador,
usado apenas para DESPROMOVER candidatos a tema. Uma palavra mal classificada
nao desaparece do indice nem da busca - apenas nao aparece como sugestao de
tema.
"""

from app.indexing.tokenizer import remover_acentos

GERUNDIO = "gerundio"
PARTICIPIO = "participio"
INFINITIVO = "infinitivo"
ADVERBIO = "adverbio"
CONJUGADO = "conjugado"
NOME = "nome"

SUFIXOS_GERUNDIO = ("ando", "endo", "indo")
SUFIXOS_PARTICIPIO = ("ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas")
SUFIXOS_INFINITIVO = ("ar", "er", "ir", "or")
SUFIXOS_CONJUGADO = (
    "aram", "eram", "iram", "avam", "iam", "ariam", "eriam", "iriam",
    "asse", "esse", "isse", "assem", "essem", "issem",
    "amos", "emos", "imos", "aria", "eria", "iria",
)

# Nomes comuns que terminam como verbos. Sem esta lista, "lugar", "professor"
# ou "energia" seriam despromovidos por engano.
NOMES_EM_AR = frozenset(
    """
    lugar escolar militar celular popular familiar particular auxiliar similar
    linear nuclear solar polar molar curricular circular regular singular
    angular muscular vascular espetacular espectacular exemplar altar
    """.split()
)
NOMES_EM_OR = frozenset(
    """
    professor autor motor valor calor amor favor setor sector fator factor
    vetor vector doutor senhor sabor tumor monitor computador trabalhador
    calculador processador servidor condutor gerador radiador reator reactor
    interior exterior superior inferior anterior posterior melhor maior menor
    """.split()
)
NOMES_EM_ER = frozenset("mulher qualquer caracter talher poder dever prazer".split())
NOMES_EM_IR = frozenset("porvir".split())
NOMES_PARTICIPIO = frozenset(
    """
    estado resultado mercado dado dados grado prado entrada chamada jornada
    camada estrada balada saida sentido partido liquido solido ruido tecido
    vestido conteudo periodo metodo modulo produto produtos derivada derivadas
    unidade velocidade quantidade medida medidas rede redes vida saude
    """.split()
)


def _sem_acento(termo: str) -> str:
    return remover_acentos(termo.lower())


def classificar(termo: str) -> str:
    palavra = _sem_acento(termo)
    if len(palavra) < 4:
        return NOME

    if palavra.endswith("mente") and len(palavra) > 6:
        return ADVERBIO

    if palavra.endswith(SUFIXOS_GERUNDIO) and len(palavra) >= 6:
        return GERUNDIO

    for sufixo in sorted(SUFIXOS_CONJUGADO, key=len, reverse=True):
        if palavra.endswith(sufixo) and len(palavra) >= len(sufixo) + 3:
            return CONJUGADO

    if palavra in NOMES_PARTICIPIO:
        return NOME
    if palavra.endswith(SUFIXOS_PARTICIPIO) and len(palavra) >= 6:
        return PARTICIPIO

    if palavra.endswith("ar") and palavra not in NOMES_EM_AR:
        return INFINITIVO
    if palavra.endswith("er") and palavra not in NOMES_EM_ER:
        return INFINITIVO
    if palavra.endswith("ir") and palavra not in NOMES_EM_IR:
        return INFINITIVO
    if palavra.endswith("or") and palavra not in NOMES_EM_OR:
        return INFINITIVO

    return NOME


def e_provavel_verbo(termo: str) -> bool:
    return classificar(termo) in (GERUNDIO, PARTICIPIO, INFINITIVO, CONJUGADO)


def serve_como_tema(termo: str) -> bool:
    return classificar(termo) in (NOME,)
