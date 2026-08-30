"""Junta as paginas do mesmo ficheiro num resultado so.

Indexar por pagina foi a decisao certa: permite levar o aluno a pagina 48 do
regulamento em vez do topo de um PDF de 61 paginas. Como APRESENTACAO, porem,
e pessima - medido em doze consultas tipicas, 54% dos lugares do top-10 eram
paginas repetidas do mesmo ficheiro, e em "regulamento interno", "plano anual
de atividades" e "projeto educativo" era um unico documento a ocupar dez
lugares.

Aqui o indice e o ranking ficam como estao. Muda so o que se mostra: cada
ficheiro aparece uma vez, pela sua melhor pagina, com as restantes por baixo.
"""

import hashlib
import re
from dataclasses import dataclass, field

# So o marcador no fim: uma origem do Moodle e
# ".../view.php?id=82783#Planificacao.pdf#pagina=8" e o "#Planificacao.pdf"
# faz parte da identidade do ficheiro.
_MARCADOR_DE_PAGINA = re.compile(r"#(?:pagina|slide)=\d+$")


def ficheiro_de(origem: str) -> str:
    """Origem sem o numero de pagina: identifica o ficheiro, nao o pedaco."""
    return _MARCADOR_DE_PAGINA.sub("", origem or "")


# Abaixo disto o texto nao identifica nada: duas paginas quase vazias
# tem o mesmo conteudo sem serem o mesmo documento.
CONTEUDO_MINIMO = 80


def impressao(texto: str) -> str:
    """Impressao digital do conteudo, para apanhar o mesmo ficheiro guardado
    em sitios diferentes.

    O professor poe a mesma ficha em quatro pastas do Moodle, e o site publica
    o mesmo PDF em dois URLs. Sao origens diferentes - e portanto documentos
    diferentes, com ids diferentes, o que esta certo - mas para quem procura
    sao a mesma folha, e ocupar quatro lugares da lista nao ajuda ninguem.
    """
    limpo = " ".join((texto or "").split())
    if len(limpo) < CONTEUDO_MINIMO:
        return ""
    return hashlib.blake2b(limpo.encode("utf-8"), digest_size=16).hexdigest()


@dataclass
class Grupo:
    documento: object
    pontuacao: float
    outras: list = field(default_factory=list)
    copias: int = 0

    @property
    def paginas(self) -> int:
        return 1 + len(self.outras)

    @property
    def tem_mais(self) -> bool:
        return bool(self.outras)


def agrupar_por_ficheiro(
    resultados: list, juntar_copias: bool = True
) -> list[Grupo]:
    """Um grupo por ficheiro, na ordem de relevancia da sua melhor pagina.

    A primeira pagina de cada ficheiro que aparece na lista ja e a melhor -
    a lista chega ordenada -, por isso basta guardar a ordem de chegada.

    Com `juntar_copias`, ficheiros distintos com conteudo identico tambem se
    juntam: e o mesmo material publicado em varios sitios.
    """
    grupos: dict[str, Grupo] = {}
    por_conteudo: dict[str, Grupo] = {}

    for documento, pontuacao in resultados:
        chave = ficheiro_de(documento.origem)
        existente = grupos.get(chave)
        if existente is not None:
            existente.outras.append((documento, pontuacao))
            continue

        marca = impressao(documento.texto) if juntar_copias else ""
        copia = por_conteudo.get(marca) if marca else None
        if copia is not None:
            copia.copias += 1
            continue

        grupo = Grupo(documento, pontuacao)
        grupos[chave] = grupo
        if marca:
            por_conteudo[marca] = grupo
    return list(grupos.values())


def achatar(grupos: list[Grupo]) -> list:
    """Volta a uma lista simples, so com a melhor pagina de cada ficheiro."""
    return [(grupo.documento, grupo.pontuacao) for grupo in grupos]
