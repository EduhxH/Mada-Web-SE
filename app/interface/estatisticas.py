import html

from app.analytics import uso

LARGURA = 620
ALTURA_BARRAS = 170


def _barras(dados: list[tuple[str, int]], titulo: str, unidade: str = "") -> str:
    if not dados:
        return f"<h2>{html.escape(titulo)}</h2><p class='vazio'>Sem dados ainda.</p>"

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
            f'fill="#24418c" opacity="0.78"></rect>'
        )
        partes.append(
            f'<text x="{x + (largura_barra - 8) / 2}" y="{y - 4}" '
            f'text-anchor="middle" font-size="10" fill="#555">{valor}{unidade}</text>'
        )
        partes.append(
            f'<text x="{x + (largura_barra - 8) / 2}" y="{ALTURA_BARRAS + 28}" '
            f'text-anchor="middle" font-size="9" fill="#777" '
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


def pagina(conexao) -> str:
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
        _barras(
            [(p, buscas) for p, buscas, _ in uso.por_participante(conexao)],
            "Buscas por participante",
        ),
        _barras(uso.disciplinas_filtradas(conexao), "Filtros de disciplina usados"),
        _tabela(
            ["participante", "buscas", "aberturas"],
            uso.por_participante(conexao),
            "Uso por participante",
        ),
        _tabela(
            ["consulta", "vezes", "sem resultado"],
            uso.consultas_populares(conexao),
            "Consultas mais frequentes",
        ),
        _tabela(
            ["consulta", "vezes"],
            uso.consultas_sem_resultado(conexao),
            "Consultas que falharam (o que falta indexar)",
        ),
    ]

    return f"""<!doctype html>
<html lang="pt-pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madalena - estatisticas</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; max-width: 680px; margin: 40px auto; padding: 0 16px; color: #1a1a1a; background: #fdfdfd; }}
h1 {{ font-size: 22px; font-weight: normal; letter-spacing: 2px; }}
h1 a {{ color: inherit; text-decoration: none; }}
h2 {{ font-size: 15px; font-weight: normal; color: #555; margin: 32px 0 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
.cartoes {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
.cartao {{ border: 1px solid #ddd; padding: 10px 14px; min-width: 96px; background: #fff; }}
.numero {{ font-size: 22px; }}
.rotulo {{ font-size: 11px; color: #777; margin-top: 2px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border-bottom: 1px solid #eee; padding: 5px 6px; text-align: left; }}
th {{ color: #777; font-weight: normal; font-size: 11px; }}
.vazio {{ color: #888; font-size: 13px; }}
footer {{ margin-top: 40px; border-top: 1px solid #ddd; padding-top: 10px; color: #aaa; font-size: 12px; }}
</style>
</head>
<body>
<h1><a href="/">Madalena</a> &middot; estatisticas</h1>
{"".join(seccoes)}
<footer>dados pseudonimizados &middot; sem nomes, sem IPs</footer>
</body>
</html>
"""
