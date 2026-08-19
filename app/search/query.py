import sqlite3

from app.indexing import storage
from app.indexing.tokenizer import tokenizar
from app.models.document import Documento
from app.search.ranker import pontuar


def buscar(
    conexao: sqlite3.Connection, consulta: str
) -> list[tuple[Documento, float]]:
    termos = set(tokenizar(consulta))
    if not termos:
        return []

    postings_por_termo = {
        termo: storage.carregar_postings(conexao, termo) for termo in termos
    }

    listas = sorted(postings_por_termo.values(), key=len)
    if not listas[0]:
        return []
    candidatos = set(listas[0])
    for postings in listas[1:]:
        candidatos &= postings.keys()
        if not candidatos:
            return []

    tamanhos = storage.carregar_tamanhos(conexao)
    total = storage.contar_documentos(conexao)
    ranqueados = pontuar(postings_por_termo, candidatos, tamanhos, total)
    return [
        (storage.carregar_documento(conexao, doc_id), pontuacao)
        for doc_id, pontuacao in ranqueados
    ]
