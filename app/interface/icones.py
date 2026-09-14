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
    "som": (
        '<path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z"/>'
        '<path d="M16 9.2a4 4 0 0 1 0 5.6"/>'
        '<path d="M18.5 6.5a7.5 7.5 0 0 1 0 11"/>'
    ),
    "sem-som": (
        '<path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z"/>'
        '<path d="M16.5 10l4 4M20.5 10l-4 4"/>'
    ),
    # ---- aparelhos, para a coluna de quem esta online ----
    "telemovel": (
        '<path d="M7 2.8h10a1.2 1.2 0 0 1 1.2 1.2v16a1.2 1.2 0 0 1-1.2 1.2H7'
        'A1.2 1.2 0 0 1 5.8 20V4A1.2 1.2 0 0 1 7 2.8Z"/>'
        '<path d="M10.5 18.5h3"/>'
    ),
    "tablet": (
        '<path d="M5 3.2h14a1 1 0 0 1 1 1v15.6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4.2'
        'a1 1 0 0 1 1-1Z"/><path d="M10.5 18h3"/>'
    ),
    "computador": (
        '<path d="M3 5h18v10H3Z"/><path d="M8.5 19h7"/><path d="M12 15v4"/>'
    ),
    # ---- painel de administracao ----
    "painel": (
        '<path d="M4 4h7v7H4ZM13 4h7v4.5h-7ZM13 10.5h7V20h-7ZM4 13h7v7H4Z"/>'
    ),
    "pessoas": (
        '<circle cx="9" cy="8" r="3.2"/>'
        '<path d="M3.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/>'
        '<path d="M16 5.5a3 3 0 0 1 0 5.6"/><path d="M17.5 15c1.8.6 3 2.2 3 5"/>'
    ),
    "pessoa": (
        '<circle cx="12" cy="8" r="3.6"/>'
        '<path d="M5 20.5c0-3.4 3-6 7-6s7 2.6 7 6"/>'
    ),
    "terminal": (
        '<path d="M3 5.5h18v13H3Z"/><path d="M7 10l2.5 2L7 14"/>'
        '<path d="M12.5 14.5H17"/>'
    ),
    "engrenagem": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2.8v2.4M12 18.8v2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7'
        'M2.8 12h2.4M18.8 12h2.4M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>'
    ),
    "jornal": (
        '<path d="M3.5 5.5h13v13h-13Z"/><path d="M16.5 9h4v7.5a2 2 0 0 1-2 2h-2Z"/>'
        '<path d="M6.5 9h7M6.5 12h7M6.5 15h4"/>'
    ),
    "imagem": (
        '<path d="M3.5 4.5h17v15h-17Z"/><circle cx="8.5" cy="9.5" r="1.6"/>'
        '<path d="M3.5 16.5 9 11.5l4 3.5 3-2.5 4.5 4"/>'
    ),
    "video": (
        '<path d="M3.5 5.5h11v13h-11Z"/><path d="M14.5 10.5 20.5 7v10l-6-3.5Z"/>'
    ),
    "ligacao": (
        '<path d="M10 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1 1"/>'
        '<path d="M14 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1-1"/>'
    ),
    "lixo": (
        '<path d="M4.5 7h15"/><path d="M9.5 7V4.5h5V7"/>'
        '<path d="M6.5 7l1 12.5h9L17 7"/><path d="M10.5 10.5v6M13.5 10.5v6"/>'
    ),
    "mais": '<path d="M12 5v14M5 12h14"/>',
    "atualizar": (
        '<path d="M20 12a8 8 0 1 1-2.5-5.8"/><path d="M20.5 4v4h-4"/>'
    ),
    "tocar": '<path d="M7 4.5 19 12 7 19.5Z"/>',
    "chave": (
        '<circle cx="8" cy="12" r="4"/><path d="M12 12h9"/>'
        '<path d="M17 12v3M20 12v2.5"/>'
    ),
    "proibido": '<circle cx="12" cy="12" r="8.5"/><path d="M6.2 6.2l11.6 11.6"/>',
    "visto": '<path d="M5 12.5 9.5 17 19 7.5"/>',
    "alerta": (
        '<path d="M12 3.8 21.5 20H2.5Z"/><path d="M12 9.5v5"/><path d="M12 17.2v.1"/>'
    ),
    "guardar": (
        '<path d="M4.5 4.5h11L19.5 8.5v11h-15Z"/><path d="M8 4.5v5h7v-5"/>'
        '<path d="M8 19.5v-6h8v6"/>'
    ),
    "campainha": (
        '<path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5.5 1.5 5.5H5S6.5 14 6.5 10Z"/>'
        '<path d="M10 18.5a2.2 2.2 0 0 0 4 0"/>'
    ),
    "relampago": '<path d="M13.5 2.5 5 13.5h5.5L10 21.5l8.5-11H13Z"/>',
    "vazio": (
        '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>'
        '<path d="M8.5 11h5"/>'
    ),
}


# Marcas de terceiros. Ficam a parte dos icones de traco porque nao seguem a
# mesma gramatica: sao silhuetas cheias, na grelha do proprio desenho, e nao
# devem ser redesenhadas em contorno para combinar com o resto - um logotipo
# alterado deixa de ser reconhecivel, e nao e nosso para mexer.
_MARCAS = {
    "github": (
        16,
        "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38"
        " 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94"
        "-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87"
        ".87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31"
        "-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32"
        "-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08"
        " 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54"
        " 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8"
        "c0-4.42-3.58-8-8-8Z"
    ),
}


def svg(nome: str, tamanho: int = 18) -> str:
    """O icone `nome` como SVG em linha, quadrado de `tamanho` pixeis."""
    marca = _MARCAS.get(nome)
    if marca is not None:
        grelha, forma = marca
        return (
            f'<svg class="ic" viewBox="0 0 {grelha} {grelha}" width="{tamanho}" '
            f'height="{tamanho}" fill="currentColor" aria-hidden="true">'
            f'<path d="{forma}"/></svg>'
        )
    forma = _FORMAS.get(nome)
    if forma is None:
        return ""
    return _ABRE.format(t=tamanho) + forma + "</svg>"


def existe(nome: str) -> bool:
    return nome in _FORMAS or nome in _MARCAS


def nomes() -> list[str]:
    return sorted(set(_FORMAS) | set(_MARCAS))
