"""Paginacao dos resultados.

A lista de resultados ja vem ordenada e completa da busca. Paginar e so
escolher a janela que se mostra - mas os limites sao onde se erra: pagina
zero, pagina para alem do fim, uma pagina a mais quando o total e multiplo
exato do tamanho. Fica tudo aqui, com testes, em vez de espalhado por
`if`s no meio do HTML.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

POR_PAGINA = 10
# Quantos numeros de pagina se mostram de cada vez. O Google mostra dez.
NUMEROS_VISIVEIS = 10


@dataclass(frozen=True)
class Janela:
    """Que fatia da lista se mostra, e onde ela cai no todo."""

    pagina: int
    total_paginas: int
    total_itens: int
    inicio: int
    fim: int

    @property
    def ha_anterior(self) -> bool:
        return self.pagina > 1

    @property
    def ha_seguinte(self) -> bool:
        return self.pagina < self.total_paginas

    def fatiar(self, itens: list) -> list:
        return itens[self.inicio:self.fim]


def calcular(total_itens: int, pagina: int, por_pagina: int = POR_PAGINA) -> Janela:
    """Janela segura para qualquer numero de pagina que venha do URL.

    A pagina chega do endereco, portanto chega o que o aluno escrever la:
    `pg=0`, `pg=-3`, `pg=99999`. Todas sao empurradas para dentro do
    intervalo em vez de darem erro - uma lista vazia com "pagina 4 de 2" no
    fundo nao ajuda ninguem.
    """
    por_pagina = max(1, por_pagina)
    if total_itens <= 0:
        return Janela(1, 1, 0, 0, 0)
    # Divisao para cima sem importar math: 21 itens de 10 em 10 sao 3 paginas,
    # 20 sao 2 - e o erro classico e dar 3 para os 20.
    total_paginas = (total_itens + por_pagina - 1) // por_pagina
    pagina = min(max(1, pagina), total_paginas)
    inicio = (pagina - 1) * por_pagina
    return Janela(
        pagina=pagina,
        total_paginas=total_paginas,
        total_itens=total_itens,
        inicio=inicio,
        fim=min(inicio + por_pagina, total_itens),
    )


def numeros(janela: Janela, visiveis: int = NUMEROS_VISIVEIS) -> list[int]:
    """Os numeros de pagina a mostrar, centrados na pagina atual.

    Perto das pontas a janela nao encolhe: desliza. Sem isso, na pagina 1 de
    50 apareciam cinco numeros e no meio apareciam dez, e a barra saltava de
    largura a cada clique.
    """
    if janela.total_paginas <= visiveis:
        return list(range(1, janela.total_paginas + 1))
    metade = visiveis // 2
    inicio = janela.pagina - metade
    inicio = max(1, min(inicio, janela.total_paginas - visiveis + 1))
    return list(range(inicio, inicio + visiveis))


def url(base_parametros: dict, pagina: int) -> str:
    """Endereco da mesma busca noutra pagina.

    A pagina 1 sai do endereco em vez de ir como `pg=1`: e a mesma pagina, e
    dois enderecos para o mesmo sitio dividiriam o registo de uso em dois.
    """
    parametros = {chave: valor for chave, valor in base_parametros.items() if valor}
    if pagina > 1:
        parametros["pg"] = str(pagina)
    return "/?" + urlencode(parametros) if parametros else "/"


def ler(bruto: str) -> int:
    """Numero de pagina vindo do URL. Qualquer disparate vale 1."""
    return int(bruto) if bruto.isdigit() and int(bruto) > 0 else 1
