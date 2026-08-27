import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from app.indexing import storage
from app.indexing.tokenizer import tokenizar
from app.models.document import Documento
from app.search import morfologia
from app.search.ranker import pontuar
from app.search.spelling import distancia_edicao, sugerir

MODO_E = "e"
MODO_QUORUM = "quorum"
MODO_OU = "ou"
MODO_VAZIO = "vazio"

# Fracao dos termos que um documento tem de conter no modo intermedio.
FRACAO_QUORUM = 0.6
# Uma correcao so e aplicada sozinha se for muito proxima e bem apoiada.
DISTANCIA_AUTOMATICA = 1
DOCUMENTOS_MINIMOS_CORRECAO = 3
# Um acerto no titulo vale mais que no corpo: o titulo diz o que o
# documento E, o corpo so diz o que ele menciona.
PESO_TITULO = 0.6


@dataclass
class ResultadoBusca:
    documentos: list[tuple[Documento, float]] = field(default_factory=list)
    modo: str = MODO_VAZIO
    sugestoes: dict[str, str] = field(default_factory=dict)
    correcao: dict[str, str] = field(default_factory=dict)
    termos_exigidos: int = 0
    termos_totais: int = 0

    def consulta_corrigida(self, consulta: str) -> str:
        trocas = {**self.sugestoes, **self.correcao}
        palavras = [
            trocas.get(palavra.lower(), palavra) for palavra in consulta.split()
        ]
        return " ".join(palavras)

    def consulta_aplicada(self, consulta: str) -> str:
        palavras = [
            self.correcao.get(palavra.lower(), palavra) for palavra in consulta.split()
        ]
        return " ".join(palavras)


_cache_vocabulario: dict[int, set[str]] = {}


def _vocabulario(conexao) -> set[str]:
    total = storage.contar_documentos(conexao)
    if total not in _cache_vocabulario:
        _cache_vocabulario.clear()
        _cache_vocabulario[total] = {
            termo for termo, _ in storage.listar_vocabulario(conexao)
        }
    return _cache_vocabulario[total]


def limpar_cache() -> None:
    _cache_vocabulario.clear()


def _juntar(conexao, formas: set[str]) -> dict[int, int]:
    """Postings de todas as formas do mesmo termo, com frequencias somadas."""
    combinado: dict[int, int] = {}
    for forma in formas:
        for doc_id, freq in storage.carregar_postings(conexao, forma).items():
            combinado[doc_id] = combinado.get(doc_id, 0) + freq
    return combinado


def _carregar(conexao, termos: set[str], expandir: bool = True):
    """Devolve (postings por termo, formas por termo)."""
    if not expandir:
        formas = {termo: {termo} for termo in termos}
    else:
        formas = morfologia.expandir(termos, _vocabulario(conexao))
    return {t: _juntar(conexao, f) for t, f in formas.items()}, formas


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


def _contagem_por_documento(postings_por_termo) -> Counter:
    """Quantos termos da consulta cada documento contem."""
    contagem: Counter = Counter()
    for postings in postings_por_termo.values():
        contagem.update(postings.keys())
    return contagem


def _sugestoes(conexao, postings_por_termo) -> dict[str, str]:
    desconhecidos = [t for t, p in postings_por_termo.items() if not p]
    if not desconhecidos:
        return {}
    vocabulario = storage.listar_vocabulario(conexao)
    encontradas = {}
    for termo in desconhecidos:
        sugestao = sugerir(termo, vocabulario)
        if sugestao:
            encontradas[termo] = sugestao
    return encontradas


def _correcao_automatica(conexao, sugestoes: dict[str, str]) -> dict[str, str]:
    """Aplica sozinha apenas o que e obviamente uma gralha.

    Distancia 1 e a palavra sugerida bem representada no indice. Tudo o resto
    fica como sugestao para o utilizador decidir.
    """
    automaticas = {}
    for errado, certo in sugestoes.items():
        if distancia_edicao(errado, certo, DISTANCIA_AUTOMATICA) > DISTANCIA_AUTOMATICA:
            continue
        if len(storage.carregar_postings(conexao, certo)) >= DOCUMENTOS_MINIMOS_CORRECAO:
            automaticas[errado] = certo
    return automaticas


def buscar_detalhado(
    conexao: sqlite3.Connection,
    consulta: str,
    disciplina: str | None = None,
    permitir_ou: bool = True,
) -> ResultadoBusca:
    termos = set(tokenizar(consulta))
    if not termos:
        return ResultadoBusca()

    postings_por_termo, formas = _carregar(conexao, termos, expandir=permitir_ou)
    sugestoes = _sugestoes(conexao, postings_por_termo)

    correcao: dict[str, str] = {}
    if sugestoes and permitir_ou:
        correcao = _correcao_automatica(conexao, sugestoes)
        if correcao:
            termos = {correcao.get(t, t) for t in termos}
            postings_por_termo, formas = _carregar(conexao, termos)
            sugestoes = {e: c for e, c in sugestoes.items() if e not in correcao}

    base = ResultadoBusca(
        sugestoes=sugestoes, correcao=correcao, termos_totais=len(termos)
    )

    restricao = (
        storage.carregar_ids_por_disciplina(conexao, disciplina)
        if disciplina
        else None
    )

    def restringir(candidatos: set[int]) -> set[int]:
        return candidatos & restricao if restricao is not None else candidatos

    # 1. todos os termos
    candidatos = restringir(_intersecao(postings_por_termo))
    modo, exigidos = MODO_E, len(termos)

    # 2. relaxamento por quorum, e so depois qualquer termo
    if not candidatos and permitir_ou and len(termos) > 1:
        contagem = _contagem_por_documento(postings_por_termo)
        minimo = max(2, math.ceil(len(termos) * FRACAO_QUORUM))
        for exigidos in range(minimo, 0, -1):
            candidatos = restringir(
                {doc for doc, n in contagem.items() if n >= exigidos}
            )
            if candidatos:
                modo = MODO_QUORUM if exigidos > 1 else MODO_OU
                break

    if not candidatos:
        return base

    tamanhos = storage.carregar_tamanhos(conexao)
    total = storage.contar_documentos(conexao)
    ranqueados = pontuar(postings_por_termo, candidatos, tamanhos, total)
    documentos = storage.carregar_documentos(
        conexao, [doc_id for doc_id, _ in ranqueados]
    )

    todas_formas = set().union(*formas.values()) if formas else set()
    base.documentos = _realcar_titulos(
        [(documentos[doc_id], pontuacao) for doc_id, pontuacao in ranqueados],
        termos,
        todas_formas,
    )
    base.modo = modo
    base.termos_exigidos = exigidos
    return base


def _realcar_titulos(resultados, termos: set[str], formas: set[str] | None = None):
    """Reordena aplicando bonus por termos presentes no titulo.

    O ranqueamento base ja aconteceu; aqui apenas se soma o bonus e reordena.
    Como os documentos ja foram carregados, nao ha custo extra de I/O.
    """
    if not termos:
        return resultados
    alvo = formas or termos
    reforcados = []
    for doc, pontuacao in resultados:
        no_titulo = set(tokenizar(doc.titulo)) & alvo
        fator = 1 + PESO_TITULO * min(1.0, len(no_titulo) / len(termos))
        reforcados.append((doc, pontuacao * fator))
    reforcados.sort(key=lambda par: par[1], reverse=True)
    return reforcados


def buscar(
    conexao: sqlite3.Connection,
    consulta: str,
    disciplina: str | None = None,
    permitir_ou: bool = True,
) -> list[tuple[Documento, float]]:
    return buscar_detalhado(conexao, consulta, disciplina, permitir_ou).documentos
