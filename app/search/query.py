import sqlite3
from dataclasses import dataclass, field

from app.indexing import storage
from app.indexing.tokenizer import tokenizar
from app.models.document import Documento
from app.search.ranker import pontuar
from app.search.spelling import sugerir

MODO_E = "e"
MODO_OU = "ou"
MODO_VAZIO = "vazio"


@dataclass
class ResultadoBusca:
    documentos: list[tuple[Documento, float]] = field(default_factory=list)
    modo: str = MODO_VAZIO
    sugestoes: dict[str, str] = field(default_factory=dict)

    def consulta_corrigida(self, consulta: str) -> str:
        palavras = [
            self.sugestoes.get(palavra.lower(), palavra)
            for palavra in consulta.split()
        ]
        return " ".join(palavras)


def _intersecao(postings_por_termo: dict[str, dict[int, int]]) -> set[int]:
    listas = sorted(postings_por_termo.values(), key=len)
    if not listas or not listas[0]:
        return set()
    candidatos = set(listas[0])
    for postings in listas[1:]:
        candidatos &= postings.keys()
        if not candidatos:
            return set()
    return candidatos


def _uniao(postings_por_termo: dict[str, dict[int, int]]) -> set[int]:
    candidatos: set[int] = set()
    for postings in postings_por_termo.values():
        candidatos |= postings.keys()
    return candidatos


def _sugestoes(
    conexao: sqlite3.Connection, postings_por_termo: dict[str, dict[int, int]]
) -> dict[str, str]:
    desconhecidos = [
        termo for termo, postings in postings_por_termo.items() if not postings
    ]
    if not desconhecidos:
        return {}
    vocabulario = storage.listar_vocabulario(conexao)
    encontradas = {}
    for termo in desconhecidos:
        sugestao = sugerir(termo, vocabulario)
        if sugestao:
            encontradas[termo] = sugestao
    return encontradas


def buscar_detalhado(
    conexao: sqlite3.Connection,
    consulta: str,
    disciplina: str | None = None,
    permitir_ou: bool = True,
) -> ResultadoBusca:
    termos = set(tokenizar(consulta))
    if not termos:
        return ResultadoBusca()

    postings_por_termo = {
        termo: storage.carregar_postings(conexao, termo) for termo in termos
    }
    sugestoes = _sugestoes(conexao, postings_por_termo)

    restricao = (
        storage.carregar_ids_por_disciplina(conexao, disciplina)
        if disciplina
        else None
    )

    modo = MODO_E
    candidatos = _intersecao(postings_por_termo)
    if restricao is not None:
        candidatos &= restricao

    if not candidatos and permitir_ou and len(termos) > 1:
        modo = MODO_OU
        candidatos = _uniao(postings_por_termo)
        if restricao is not None:
            candidatos &= restricao

    if not candidatos:
        return ResultadoBusca(sugestoes=sugestoes)

    tamanhos = storage.carregar_tamanhos(conexao)
    total = storage.contar_documentos(conexao)
    ranqueados = pontuar(postings_por_termo, candidatos, tamanhos, total)

    documentos = storage.carregar_documentos(
        conexao, [doc_id for doc_id, _ in ranqueados]
    )
    return ResultadoBusca(
        documentos=[
            (documentos[doc_id], pontuacao) for doc_id, pontuacao in ranqueados
        ],
        modo=modo,
        sugestoes=sugestoes,
    )


def buscar(
    conexao: sqlite3.Connection,
    consulta: str,
    disciplina: str | None = None,
    permitir_ou: bool = True,
) -> list[tuple[Documento, float]]:
    return buscar_detalhado(conexao, consulta, disciplina, permitir_ou).documentos
