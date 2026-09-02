"""Icones de traco, desenhados aqui dentro.

Sao SVG em linha e nao um tipo de letra de icones nem ficheiros soltos, por
tres razoes:

- **Nao ha pedido nenhum.** Um tipo de letra de icones sao 30-80 KB que o
  aluno espera antes de ver o primeiro icone; assim vao no HTML que ja vinha
  a caminho.
- **Herdam a cor do texto.** `stroke="currentColor"` faz o icone mudar de cor
  com o tema sem uma linha de CSS por icone.
- **Nao dependem de ninguem.** Vale a mesma regra do resto do projeto: nada
  que obrigue a ir buscar coisas a servidores alheios.

Todos partilham a mesma gramatica - grelha de 24, traco de 1.5, pontas e
cantos redondos - que e o que os faz parecer da mesma familia.
"""

_ABRE = (
    '<svg class="ic" viewBox="0 0 24 24" width="{t}" height="{t}" fill="none" '
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
)

_FORMAS = {
    "lupa": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "pasta": (
        '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4l2 2.5h9A1.5 1.5 0 0 1 21 10v8'
        'a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18Z"/>'
    ),
    "ficheiro": (
        '<path d="M14 3H7a1.5 1.5 0 0 0-1.5 1.5v15A1.5 1.5 0 0 0 7 21h10'
        'a1.5 1.5 0 0 0 1.5-1.5V7.5Z"/><path d="M14 3v4.5h4.5"/>'
        '<path d="M9 13h6M9 16.5h4"/>'
    ),
    "relogio": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.75"/>',
    "globo": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/>'
        '<path d="M12 3.5c2.2 2.4 3.3 5.4 3.3 8.5S14.2 18.1 12 20.5'
        'c-2.2-2.4-3.3-5.4-3.3-8.5S9.8 5.9 12 3.5Z"/>'
    ),
    "seta-esq": '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
    "seta-dir": '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
    "sol": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4'
        'M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>'
    ),
    "lua": '<path d="M20 14.2A8.5 8.5 0 0 1 9.8 4 8.5 8.5 0 1 0 20 14.2Z"/>',
    "sair": (
        '<path d="M14 20H6.5A1.5 1.5 0 0 1 5 18.5v-13A1.5 1.5 0 0 1 6.5 4H14"/>'
        '<path d="M17 15.5 20.5 12 17 8.5"/><path d="M20.5 12H10"/>'
    ),
    "grafico": (
        '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'
    ),
    "brilho": (
        '<path d="M12 3.5 13.7 9 19 10.7 13.7 12.4 12 17.9 10.3 12.4 5 10.7'
        ' 10.3 9Z"/><path d="M18.5 16.5 19.2 18.6 21.3 19.3 19.2 20 18.5 22.1'
        ' 17.8 20 15.7 19.3 17.8 18.6Z"/>'
    ),
    "olho": (
        '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12'
        ' 2.5 12Z"/><circle cx="12" cy="12" r="3"/>'
    ),
    "fora": (
        '<path d="M14 4h6v6"/><path d="M20 4 11 13"/>'
        '<path d="M18 14.5v4A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5'
        'v-11A1.5 1.5 0 0 1 5.5 6h4"/>'
    ),
    "cruz": '<path d="M6 6l12 12M18 6 6 18"/>',
    "vazio": (
        '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>'
        '<path d="M8.5 11h5"/>'
    ),
}


def svg(nome: str, tamanho: int = 18) -> str:
    """O icone `nome` como SVG em linha, quadrado de `tamanho` pixeis."""
    forma = _FORMAS.get(nome)
    if forma is None:
        return ""
    return _ABRE.format(t=tamanho) + forma + "</svg>"


def existe(nome: str) -> bool:
    return nome in _FORMAS


def nomes() -> list[str]:
    return sorted(_FORMAS)
