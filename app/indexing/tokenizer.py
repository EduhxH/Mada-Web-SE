import re
import unicodedata

STOP_WORDS = frozenset(
    """
    a as o os um uma uns umas
    de da das do dos
    e em na nas no nos num numa
    que se com por para pela pelas pelo pelos
    ao aos
    mas mais como ou nao sim
    seu sua seus suas
    ele ela eles elas eu nos voce
    este esta estes estas isto
    esse essa esses essas isso
    aquele aquela aqueles aquelas aquilo
    ser sao foi era ha ja tambem esta estao
    the of and to in is it for on as
    """.split()
)

# Palavras com que se faz uma PERGUNTA, e que nada dizem sobre o assunto dela.
#
# Sao aqui um problema pior do que parece, e por uma razao do avesso: numa
# coleccao de documentos escolares estas palavras sao RARAS - "vejo" aparece
# em 1 documento, "devo" em 3, "posso" e "tenho" em 5 - e o TF-IDF premeia
# exactamente o que e raro. "Quantas faltas posso ter" era decidido por
# "quantas" e "posso", e devolvia um manual de TIC.
#
# Os alunos escrevem perguntas. Sem isto, quanto mais natural a pergunta,
# pior a resposta.
PALAVRAS_DE_PERGUNTA = frozenset(
    """
    quando onde quanto quanta quantos quantas qual quais quem porque
    posso preciso quero tenho vejo devo faco sei queria gostava consigo
    meu minha meus minhas
    ter tem temos fazer faz pode podem deve devem saber sabe estar
    ver procurar encontrar achar arranjar baixar descarregar
    """.split()
)

STOP_WORDS = STOP_WORDS | PALAVRAS_DE_PERGUNTA

_PADRAO_TOKEN = re.compile(r"[a-z0-9]+")
# FichaRevisoes -> Ficha Revisoes; GestCampeonato -> Gest Campeonato.
# Sem isto, nomes de ficheiro sem espacos viram um unico token inutil.
# So minuscula seguida de maiuscula e camelCase. Incluir digitos partia
# "3D" em "3" e "D", e o "D" caia por ser curto: a modelacao 3D ficava
# indexada como "3".
_PADRAO_CAMEL = re.compile(r"([a-z])([A-Z])")

COMPRIMENTO_MINIMO = 2

# Ordinal reduzido ao numero: "10o ano" e "10 ano" sao a mesma coisa para
# quem procura, mas eram termos diferentes no indice - por isso "manuais
# adotados 10 ano" devolvia o 12o ano em primeiro lugar. O "º" ja chega aqui
# como "o", cortesia da normalizacao NFKD.
_ORDINAL = re.compile(r"^(\d+)[oa]$")


def _reduzir_ordinal(token: str) -> str:
    casado = _ORDINAL.match(token)
    return casado.group(1) if casado else token


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def tokenizar(texto: str, remover_stop_words: bool = True) -> list[str]:
    separado = _PADRAO_CAMEL.sub(lambda m: m.group(1) + " " + m.group(2), texto)
    normalizado = remover_acentos(separado.lower())
    # O comprimento minimo existe para letras soltas, que nada dizem. Um
    # digito solto diz: a escola organiza-se por modulos, e "modulo 3" perdia
    # o 3 - a parte que distinguia a consulta.
    tokens = [
        reduzido
        for t in _PADRAO_TOKEN.findall(normalizado)
        for reduzido in (_reduzir_ordinal(t),)
        if len(reduzido) >= COMPRIMENTO_MINIMO or reduzido.isdigit()
    ]
    if remover_stop_words:
        tokens = [t for t in tokens if t not in STOP_WORDS]
    return tokens
