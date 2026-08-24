from app.indexing.tokenizer import tokenizar
from app.models.document import Documento


def buscar_ingenua(consulta: str, documentos: list[Documento]) -> list[Documento]:
    termos = tokenizar(consulta)
    if not termos:
        return []
    resultados = []
    for doc in documentos:
        tokens_do_doc = set(tokenizar(doc.texto_pesquisavel))
        if all(termo in tokens_do_doc for termo in termos):
            resultados.append(doc)
    return resultados
