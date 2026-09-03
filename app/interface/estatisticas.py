import html

from app.analytics import uso
from app.interface import estilo, icones, movimento, som

LARGURA = 620
ALTURA_BARRAS = 170


# Abaixo disto um grafico de barras nao compara nada: com dois dias fica uma
# barra sozinha a ocupar a altura toda, o que parece avaria e nao informacao.
MINIMO_PARA_GRAFICO = 3


def _seccao(titulo: str, corpo: str) -> str:
    return f'<section><p class="olho">{html.escape(titulo)}</p>{corpo}</section>'


def _barras(dados: list[tuple[str, int]], titulo: str) -> str:
    """Barras cheias assentes numa linha, como no desenho.

    Nao ha eixo nem grelha: o valor vai por cima de cada barra e o rotulo por
    baixo. Numa pagina sem cor, uma grelha so acrescentaria ruido cinzento.
    """
    if not dados:
        return _seccao(titulo, '<p class="lado-nota">Sem dados ainda.</p>')

    if len(dados) < MINIMO_PARA_GRAFICO:
        linhas = " &middot; ".join(
            f"<b>{valor}</b> em {html.escape(str(rotulo))}" for rotulo, valor in dados
        )
        return _seccao(titulo, f'<p class="resumo-barras">{linhas}</p>')

    maximo = max(valor for _, valor in dados) or 1
    passo = LARGURA / len(dados)
    largura = min(56.0, passo - 8)
    partes = [
        f'<div class="grafico"><svg viewBox="0 0 {LARGURA} {ALTURA_BARRAS + 44}"'
        ' width="100%" role="img" aria-label="'
        f'{html.escape(titulo)}">'
    ]
    for indice, (rotulo, valor) in enumerate(dados):
        altura = max(2, int(valor / maximo * ALTURA_BARRAS))
        x = indice * passo + (passo - largura) / 2
        y = ALTURA_BARRAS - altura + 16
        meio = x + largura / 2
        partes.append(
            f'<rect x="{x:.1f}" y="{y}" width="{largura:.1f}" height="{altura}" '
            'fill="var(--texto)"></rect>'
        )
        partes.append(
            f'<text x="{meio:.1f}" y="{y - 6}" text-anchor="middle" '
            'font-size="10" font-family="var(--mono)" '
            f'fill="var(--texto-3)">{valor}</text>'
        )
        partes.append(
            f'<text x="{meio:.1f}" y="{ALTURA_BARRAS + 32}" text-anchor="middle" '
            'font-size="9" font-family="var(--mono)" fill="var(--texto-4)" '
            f'transform="rotate(-32 {meio:.1f} {ALTURA_BARRAS + 32})">'
            f"{html.escape(str(rotulo)[:14])}</text>"
        )
    partes.append("</svg></div>")
    return _seccao(titulo, "".join(partes))


def _lista(linhas, titulo: str, vazio: str = "Sem dados ainda.") -> str:
    """Lista numerada com o valor a direita, em vez de tabela.

    A tabela de tres colunas nao cabia no telemovel sem deslizar de lado; a
    lista quebra sozinha e diz o mesmo.
    """
    if not linhas:
        return _seccao(titulo, f'<p class="lado-nota">{html.escape(vazio)}</p>')
    itens = []
    for numero, linha in enumerate(linhas, start=1):
        etiqueta = html.escape(str(linha[0]))
        valor = linha[1] if len(linha) > 1 else ""
        itens.append(
            f"<li><span>{etiqueta}</span>"
            f'<span class="ordem">{html.escape(str(valor))}</span></li>'
        )
    return _seccao(titulo, f'<ol class="lista-topo">{"".join(itens)}</ol>')


def _metrica(rotulo: str, valor: str) -> str:
    return (
        f'<div class="metrica"><span class="numero">{html.escape(valor)}</span>'
        f'<span class="rotulo">{html.escape(rotulo)}</span></div>'
    )


def pagina(conexao, administrador: bool = False) -> str:
    # Sem privilegios, so agregados: nada que identifique um colega.
    minimo = 1 if administrador else 2
    dados = uso.resumo(conexao)
    metricas = "".join(
        [
            _metrica("buscas", str(dados["buscas"])),
            _metrica("participantes", str(dados["participantes"])),
            _metrica("dias com uso", str(dados["dias"])),
            _metrica("documentos abertos", str(dados["aberturas"])),
            _metrica("sem resultado", f"{dados['taxa_vazias']:.0f}%"),
            _metrica("parciais (OU)", f"{dados['taxa_parciais']:.0f}%"),
            _metrica("taxa de abertura", f"{dados['taxa_abertura']:.0f}%"),
            _metrica("sugestões aceites", str(dados["sugestoes_aceites"])),
        ]
    )

    duas = [
        _barras(uso.por_dia(conexao), "Buscas por dia"),
        _lista(
            uso.consultas_populares(conexao, minimo_participantes=minimo),
            "Mais frequentes",
        ),
    ]
    resto = [
        _barras(uso.disciplinas_filtradas(conexao), "Filtros de disciplina usados"),
        _lista(
            uso.consultas_sem_resultado(conexao, minimo_participantes=minimo),
            "O que falhou",
            "Nenhuma busca ficou sem resposta.",
        ),
    ]
    if administrador:
        resto.append(
            _lista(uso.por_participante(conexao), "Uso por participante")
        )
        rodape_nota = ""
    else:
        rodape_nota = (
            '<p class="lado-nota">Consultas feitas por uma só pessoa não são'
            " mostradas, para não identificar ninguém.</p>"
        )

    return (
        f"{estilo.cabeca('Madalena - estatísticas')}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{estilo.acoes('estatisticas')}"
        "</div></header>\n"
        '<div class="pagina-apoio">'
        f'<a class="voltar" href="/">{icones.svg("seta-esq", 14)}voltar à busca</a>'
        '<p class="olho">Visão geral</p>'
        '<h1 class="display h-grande">Estatísticas</h1>'
        f'<div class="metricas">{metricas}</div>'
        f'<div class="duas-colunas">{"".join(duas)}</div>'
        f'<div class="duas-colunas">{"".join(resto)}</div>'
        f"{rodape_nota}"
        "</div>\n"
        '<footer class="rodape">'
        "<span>Dados pseudonimizados</span>"
        "<span>Sem nomes, sem IPs</span>"
        '<span><a href="/privacidade">Os teus dados</a></span>'
        f"{estilo.credito()}"
        "</footer>\n"
        f"<script>{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}{som.marcacao()}\n"
        "</body>\n</html>"
    )
