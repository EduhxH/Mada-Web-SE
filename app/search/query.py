import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from app.indexing import storage
from app.indexing.tokenizer import tokenizar
from app.models.document import Documento
from app.search import morfologia, sinonimos
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
# documento E, o corpo so diz o que ele menciona. Um documento intitulado
# "Calendario Escolar" e o calendario, mesmo que nunca repita a expressao;
# o TF-IDF sozinho preferia-lhe um regulamento que a menciona em prosa.
#
# 0.6 era demasiado timido. Varrido de 0 a 10 contra avaliacao/consultas.json:
# o ganho cresce ate 3.0 e ai estabiliza (top-1 de 8/16 para 11/16, MRR de
# 0.58 para 0.73), sem nenhuma consulta a piorar. Acima de 3.0 nada muda.
# Multiplicativo e nao aditivo por ser invariante a escala: as pontuacoes
# base variam duas ordens de grandeza entre consultas, e uma constante
# somada esmagaria as diferencas nas mais baixas.
PESO_TITULO = 3.0


@dataclass
class ResultadoBusca:
    documentos: list[tuple[Documento, float]] = field(default_factory=list)
    modo: str = MODO_VAZIO
    sugestoes: dict[str, str] = field(default_factory=dict)
    correcao: dict[str, str] = field(default_factory=dict)
    termos_exigidos: int = 0
    termos_totais: int = 0
    # Disciplina lida da propria pergunta, para a interface poder mostrar o
    # filtro que foi aplicado sozinho e oferecer maneira de o desligar.
    disciplina_detetada: str = ""
    ordenado_por_recencia: bool = False
    # Paginas do mesmo ficheiro juntas: `documentos` traz a melhor de cada
    # uma, `grupos` guarda as restantes para a interface as poder oferecer.
    grupos: list = field(default_factory=list)

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
_cache_frequencias: dict[int, dict[str, int]] = {}


def _frequencias(conexao) -> dict[str, int]:
    """{termo: em quantos documentos aparece} - o teto dos sinonimos usa isto."""
    total = storage.contar_documentos(conexao)
    if total not in _cache_frequencias:
        _cache_frequencias.clear()
        _cache_frequencias[total] = dict(storage.listar_vocabulario(conexao))
    return _cache_frequencias[total]


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
    _cache_frequencias.clear()


def _juntar(conexao, formas: set[str]) -> dict[int, int]:
    """Postings de todas as formas do mesmo termo, com frequencias somadas."""
    combinado: dict[int, int] = {}
    for forma in formas:
        for doc_id, freq in storage.carregar_postings(conexao, forma).items():
            combinado[doc_id] = combinado.get(doc_id, 0) + freq
    return combinado


def _carregar(
    conexao, termos: set[str], expandir: bool = True, calao: bool = False
):
    """Devolve (postings por termo, formas por termo).

    `calao` liga os sinonimos da escola. So se liga quando ha filtro de
    disciplina: medido, alargar "sebenta" para "manual" no corpus inteiro
    empurrava a sebenta certa do 1o para o 8o lugar, enquanto dentro de uma
    disciplina o mesmo alargamento traz o guiao que o aluno chamou de ficha.
    """
    if not expandir:
        formas = {termo: {termo} for termo in termos}
    else:
        formas = morfologia.expandir(termos, _vocabulario(conexao))
        # O calao da escola entra depois das formas: cada sinonimo traz
        # tambem as suas proprias variantes de numero e de grafia.
        if calao:
            vocabulario = _vocabulario(conexao)
            parentes = sinonimos.expandir(
                termos, _frequencias(conexao), storage.contar_documentos(conexao)
            )
            for termo, irmaos in parentes.items():
                for irmao in irmaos:
                    formas[termo] |= morfologia.variantes(irmao, vocabulario)
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

    postings_por_termo, formas = _carregar(
        conexao, termos, expandir=permitir_ou, calao=bool(disciplina)
    )
    sugestoes = _sugestoes(conexao, postings_por_termo)

    correcao: dict[str, str] = {}
    if sugestoes and permitir_ou:
        correcao = _correcao_automatica(conexao, sugestoes)
        if correcao:
            termos = {correcao.get(t, t) for t in termos}
            postings_por_termo, formas = _carregar(
                conexao, termos, calao=bool(disciplina)
            )
            sugestoes = {e: c for e, c in sugestoes.items() if e not in correcao}

    base = ResultadoBusca(
        sugestoes=sugestoes, correcao=correcao, termos_totais=len(termos)
    )

    # Aceita uma disciplina ou varias: quem escolhe no menu quer so aquela,
    # quem a escreveu na pergunta merece o beneficio da duvida e leva junto
    # os documentos gerais da escola.
    restricao = None
    if disciplina:
        nomes = [disciplina] if isinstance(disciplina, str) else list(disciplina)
        restricao = set()
        for nome in nomes:
            restricao |= storage.carregar_ids_por_disciplina(conexao, nome)

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
