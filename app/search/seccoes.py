import re
from dataclasses import dataclass

from app.indexing.tokenizer import remover_acentos

HORARIOS = "horarios"
MATERIAL = "material"
REGULAMENTOS = "regulamentos"
SITE = "site"


@dataclass(frozen=True)
class Seccao:
    chave: str
    titulo: str


SECCOES = {
    HORARIOS: Seccao(HORARIOS, "Horarios"),
    MATERIAL: Seccao(MATERIAL, "Fichas e materiais"),
    REGULAMENTOS: Seccao(REGULAMENTOS, "Regulamentos e informacoes"),
    SITE: Seccao(SITE, "Paginas do site"),
}

DISCIPLINAS_HORARIO = frozenset({"horarios", "horario"})

# Fronteiras de palavra para nao apanhar "ata" dentro de "data" ou
# "matriz" dentro de outra coisa qualquer.
_PADRAO_REGULAMENTO = re.compile(
    r"\b("
    r"regulament\w*|criterio\w*|planifica\w*|justificac\w*|matriz\w*|"
    r"estatuto\w*|ata|atas|projeto educativo|politica\w*|privacidade|"
    r"conduta|calendario\w*|circular\w*|comunicado\w*|aviso\w*|edital\w*|"
    r"dossier\w*|agenda\w*|dossie\w*"
    r")\b"
)


def classificar(doc) -> str:
    disciplina = remover_acentos(doc.disciplina.lower())
    if disciplina in DISCIPLINAS_HORARIO:
        return HORARIOS

    titulo = remover_acentos(doc.titulo.lower())
    if _PADRAO_REGULAMENTO.search(titulo):
        return REGULAMENTOS

    if doc.origem.startswith(("http://", "https://")):
        return SITE

    return MATERIAL


def agrupar(resultados) -> list[tuple[Seccao, list]]:
    """Agrupa mantendo a ordem de relevancia dentro de cada seccao.

    As seccoes sao ordenadas pela melhor pontuacao que contem, para que a
    seccao do resultado mais relevante apareca primeiro.
    """
    grupos: dict[str, list] = {}
    melhor: dict[str, float] = {}
    for doc, pontuacao in resultados:
        chave = classificar(doc)
        grupos.setdefault(chave, []).append((doc, pontuacao))
        if pontuacao > melhor.get(chave, float("-inf")):
            melhor[chave] = pontuacao

    ordenadas = sorted(grupos, key=lambda chave: melhor[chave], reverse=True)
    return [(SECCOES[chave], grupos[chave]) for chave in ordenadas]


def filtrar(resultados, chave: str) -> list:
    return [par for par in resultados if classificar(par[0]) == chave]


def titulo_da(chave: str) -> str:
    seccao = SECCOES.get(chave)
    return seccao.titulo if seccao else ""
