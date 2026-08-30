from dataclasses import dataclass

from app.indexing.tokenizer import remover_acentos
from app.models.classificacao import e_administrativo

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

# Material de disciplina vive no Moodle. Antes do conector, chegava como
# ficheiro local e bastava perguntar se a origem era um URL; hoje tambem e
# um URL, e a pergunta passou a ser de que servidor vem.
ANFITRIOES_MATERIAL = ("moodle.",)


def e_material(origem: str) -> bool:
    return any(marca in origem.lower() for marca in ANFITRIOES_MATERIAL)


def classificar(doc) -> str:
    disciplina = remover_acentos(doc.disciplina.lower())
    if disciplina in DISCIPLINAS_HORARIO:
        return HORARIOS

    titulo = remover_acentos(doc.titulo.lower())
    if e_administrativo(titulo):
        return REGULAMENTOS

    if e_material(doc.origem):
        return MATERIAL

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
