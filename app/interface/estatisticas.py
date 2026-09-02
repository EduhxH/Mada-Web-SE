import html

from app.analytics import uso
from app.interface import estilo, movimento

LARGURA = 620
ALTURA_BARRAS = 170


# Abaixo disto um grafico de barras nao compara nada: com dois dias fica uma
# barra sozinha a ocupar a altura toda, o que parece avaria e nao informacao.
MINIMO_PARA_GRAFICO = 3


def _barras(dados: list[tuple[str, int]], titulo: str, unidade: str = "") -> str:
    if not dados:
        return f"<h2>{html.escape(titulo)}</h2><p class='vazio'>Sem dados ainda.</p>"

    if len(dados) < MINIMO_PARA_GRAFICO:
        linhas = " &middot; ".join(
            f"<b>{valor}</b> em {html.escape(str(rotulo))}" for rotulo, valor in dados
        )
        return f"<h2>{html.escape(titulo)}</h2><p class='resumo'>{linhas}</p>"

    maximo = max(valor for _, valor in dados) or 1
    largura_barra = min(56, (LARGURA - 40) // max(len(dados), 1))
    partes = [
        f"<h2>{html.escape(titulo)}</h2>",
        f'<svg viewBox="0 0 {LARGURA} {ALTURA_BARRAS + 46}" '
        f'width="100%" role="img">',
    ]
    for indice, (rotulo, valor) in enumerate(dados):
        altura = int(valor / maximo * ALTURA_BARRAS)
        x = 24 + indice * largura_barra
        y = ALTURA_BARRAS - altura + 14
        partes.append(
            f'<rect x="{x}" y="{y}" width="{largura_barra - 8}" height="{altura}" '
            f'fill="var(--realce)" opacity="0.85"></rect>'
        )
        partes.append(
            f'<text x="{x + (largura_barra - 8) / 2}" y="{y - 4}" '
            f'text-anchor="middle" font-size="10" fill="var(--texto-suave)">{valor}{unidade}</text>'
        )
        partes.append(
            f'<text x="{x + (largura_barra - 8) / 2}" y="{ALTURA_BARRAS + 28}" '
            f'text-anchor="middle" font-size="9" fill="var(--texto-meta)" '
            f'transform="rotate(-35 {x + (largura_barra - 8) / 2} '
            f'{ALTURA_BARRAS + 28})">{html.escape(str(rotulo)[:14])}</text>'
        )
    partes.append("</svg>")
    return "\n".join(partes)


def _tabela(cabecalhos: list[str], linhas, titulo: str) -> str:
    if not linhas:
        return f"<h2>{html.escape(titulo)}</h2><p class='vazio'>Sem dados ainda.</p>"
    saida = [f"<h2>{html.escape(titulo)}</h2>", "<table>", "<tr>"]
    saida += [f"<th>{html.escape(c)}</th>" for c in cabecalhos]
    saida.append("</tr>")
    for linha in linhas:
        saida.append("<tr>")
        saida += [f"<td>{html.escape(str(v if v is not None else '-'))}</td>" for v in linha]
        saida.append("</tr>")
    saida.append("</table>")
    return "\n".join(saida)


def _cartao(rotulo: str, valor: str) -> str:
    return (
        f'<div class="cartao"><div class="numero">{html.escape(valor)}</div>'
        f'<div class="rotulo">{html.escape(rotulo)}</div></div>'
    )


def pagina(conexao, administrador: bool = False) -> str:
    # Sem privilegios, so agregados: nada que identifique um colega.
    minimo = 1 if administrador else 2
    dados = uso.resumo(conexao)
    cartoes = "".join(
        [
            _cartao("buscas", str(dados["buscas"])),
            _cartao("participantes", str(dados["participantes"])),
            _cartao("dias com uso", str(dados["dias"])),
            _cartao("documentos abertos", str(dados["aberturas"])),
            _cartao("sem resultado", f"{dados['taxa_vazias']:.0f}%"),
            _cartao("parciais (OU)", f"{dados['taxa_parciais']:.0f}%"),
            _cartao("taxa de abertura", f"{dados['taxa_abertura']:.0f}%"),
            _cartao("sugestoes aceites", str(dados["sugestoes_aceites"])),
        ]
    )

    seccoes = [
        f'<div class="cartoes">{cartoes}</div>',
        _barras(uso.por_dia(conexao), "Buscas por dia"),
        _barras(uso.disciplinas_filtradas(conexao), "Filtros de disciplina usados"),
        _tabela(
            ["consulta", "vezes", "sem resultado"],
            uso.consultas_populares(conexao, minimo_participantes=minimo),
            "Consultas mais frequentes",
        ),
        _tabela(
            ["consulta", "vezes"],
            uso.consultas_sem_resultado(conexao, minimo_participantes=minimo),
            "Consultas que falharam (o que falta indexar)",
        ),
    ]
    if administrador:
        seccoes.insert(
            4,
            _tabela(
                ["participante", "buscas", "aberturas"],
                uso.por_participante(conexao),
                "Uso por participante",
            ),
        )
    else:
        seccoes.append(
            '<p class="vazio">Consultas feitas por uma só pessoa não são'
            " mostradas, para não identificar ninguém.</p>"
        )

    return (
        f"{estilo.cabeca('Madalena - estatísticas')}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{estilo.acoes(voltar=True)}"
        "</div></header>\n"
        '<main><div class="coluna">'
        f'<h1 class="titulo-pagina">estatísticas</h1>{"".join(seccoes)}'
        "</div></main>\n"
        "<footer>dados pseudonimizados &middot; sem nomes, sem IPs</footer>\n"
        f"<script>{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}\n"
        "</body>\n</html>"
    )
