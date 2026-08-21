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

_PADRAO_TOKEN = re.compile(r"[a-z0-9]+")

COMPRIMENTO_MINIMO = 2


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def tokenizar(texto: str, remover_stop_words: bool = True) -> list[str]:
    normalizado = remover_acentos(texto.lower())
    tokens = [
        t for t in _PADRAO_TOKEN.findall(normalizado)
        if len(t) >= COMPRIMENTO_MINIMO
    ]
    if remover_stop_words:
        tokens = [t for t in tokens if t not in STOP_WORDS]
    return tokens
