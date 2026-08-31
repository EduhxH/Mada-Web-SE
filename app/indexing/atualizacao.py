"""Atualizacao do corpus: rastrear, reindexar e dizer o que mudou.

O relatorio de alteracoes so e possivel porque os ids sao estaveis (derivados
da origem). Com ids sequenciais, comparar duas indexacoes nao diria nada.
"""

from dataclasses import dataclass, field
from pathlib import Path

from app.crawler.local_source import Relatorio, carregar
from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.search import query

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
RAIZ_CORPUS = Path("data") / "raw"


@dataclass
class Alteracoes:
    novos: list[tuple[int, str]] = field(default_factory=list)
    removidos: list[tuple[int, str]] = field(default_factory=list)
    alterados: list[tuple[int, str]] = field(default_factory=list)
    mantidos: int = 0

    @property
    def houve_mudanca(self) -> bool:
        return bool(self.novos or self.removidos or self.alterados)

    def resumo(self) -> str:
        return (
            f"{len(self.novos)} novos, {len(self.alterados)} alterados, "
            f"{len(self.removidos)} removidos, {self.mantidos} inalterados"
        )


def _instantaneo(caminho: Path) -> dict[int, tuple[str, int]]:
    """id -> (titulo, tamanho do texto) do indice atual, se existir."""
    if not caminho.exists():
        return {}
    conexao = storage.abrir(caminho)
    try:
        return {
            linha[0]: (linha[1], linha[2])
            for linha in conexao.execute(
                "SELECT id, titulo, LENGTH(texto) FROM documents"
            )
        }
    finally:
        conexao.close()


def _comparar(antes: dict, documentos: list) -> Alteracoes:
    alteracoes = Alteracoes()
    agora = {doc.id: (doc.titulo, len(doc.texto)) for doc in documentos}

    for doc_id, (titulo, tamanho) in agora.items():
        anterior = antes.get(doc_id)
        if anterior is None:
            alteracoes.novos.append((doc_id, titulo))
        elif anterior[1] != tamanho:
            alteracoes.alterados.append((doc_id, titulo))
        else:
            alteracoes.mantidos += 1

    for doc_id, (titulo, _) in antes.items():
        if doc_id not in agora:
            alteracoes.removidos.append((doc_id, titulo))

    return alteracoes


def reindexar(
    raiz: Path = RAIZ_CORPUS, banco: Path = CAMINHO_BANCO
) -> tuple[Alteracoes, Relatorio, int]:
    """Reindexa e devolve (alteracoes, relatorio de ingestao, termos unicos)."""
    antes = _instantaneo(banco)
    documentos, relatorio = carregar(raiz)
    if not documentos:
        return Alteracoes(), relatorio, 0

    indice, tamanhos = construir_indice(documentos)
    banco.parent.mkdir(parents=True, exist_ok=True)
    conexao = storage.abrir(banco)
    try:
        storage.salvar_indice(conexao, documentos, indice, tamanhos)
    finally:
        conexao.close()

    # As caches da busca guardam vocabulario, frequencias e tamanhos por
    # contagem de documentos. Reindexar sem contagem nova - por exemplo
    # depois de um ficheiro ser alterado - deixava-as a servir o corpus
    # antigo no mesmo processo.
    query.limpar_cache()

    return _comparar(antes, documentos), relatorio, len(indice)
