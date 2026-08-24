from collections import Counter

from app.indexing.tokenizer import tokenizar
from app.models.document import Documento


def construir_indice(
    documentos: list[Documento],
) -> tuple[dict[str, dict[int, int]], dict[int, int]]:
    indice: dict[str, dict[int, int]] = {}
    tamanhos: dict[int, int] = {}
    for doc in documentos:
        tokens = tokenizar(doc.texto_pesquisavel)
        tamanhos[doc.id] = len(tokens)
        for termo, freq in Counter(tokens).items():
            indice.setdefault(termo, {})[doc.id] = freq
    return indice, tamanhos
