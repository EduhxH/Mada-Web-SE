"""O que faz um documento ser administrativo, de codigo, ou de conteudo.

Vive em `models` de proposito: e uma propriedade do **documento**, nao da
busca nem da indexacao. Antes, esta lista estava em `app/search/temas.py` e o
`storage.py` importava-a de dentro das funcoes para fugir a um import
circular - a camada de baixo a saber da camada de cima. Aqui, ambas importam
da mesma base e a seta aponta sempre para baixo.
"""

import re

# Titulos que denunciam documento administrativo: regulamentos, planificacoes,
# criterios. Sao sobre a organizacao da escola, nao sobre a materia.
PADROES_ADMINISTRATIVOS = (
    "planificacao",
    "planif",
    "criterios",
    "justificacao",
    "agenda",
    "dossier",
    "sumario",
    "matriz",
    "regulamento",
    "ata",
)

# Padroes extra que so fazem sentido para o utilizador final (seccoes da
# interface), nao para excluir da extracao de temas.
PADROES_INFORMATIVOS = (
    "estatuto",
    "projeto educativo",
    "politica",
    "privacidade",
    "conduta",
    "calendario",
    "circular",
    "comunicado",
    "aviso",
    "edital",
)

# Ficheiros de codigo-fonte: o vocabulario e de identificadores
# (txtnome, namespace, conn), nao de materia de estudo.
EXTENSOES_CODIGO = (".cs", ".designer", ".resx", ".config")


def _alternativa(padroes) -> str:
    return "|".join(
        padrao.replace(" ", r"\s+") + r"\w*" if padrao.isalpha() else padrao
        for padrao in padroes
    )


# Com fronteiras de palavra, para "ata" nao apanhar "d(ata)" nem
# "matriz" aparecer dentro de outra palavra qualquer.
PADRAO_ADMINISTRATIVO = re.compile(
    r"\b(" + _alternativa(PADROES_ADMINISTRATIVOS + PADROES_INFORMATIVOS) + r")\b"
)


def e_administrativo(titulo: str) -> bool:
    """Titulo ja normalizado (minusculas, sem acentos)."""
    return bool(PADRAO_ADMINISTRATIVO.search(titulo))
