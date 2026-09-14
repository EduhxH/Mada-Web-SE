"""Marcacao simples para os textos da newsletter, e a sua traducao para HTML.

Porque nao um editor visual: um editor de texto rico a serio sao centenas de
kilobytes de biblioteca, e a regra do projeto e nao ir buscar nada a servidores
alheios - teria de ser auto-alojado e mantido. Mas o motivo verdadeiro e outro:
um editor visual produz HTML, e HTML escrito por quem quer que seja e HTML que
tem de ser desinfetado antes de ser mostrado. Desinfetar HTML bem e difficil e
falha-se em silencio. Uma marcacao pequena inverte o problema - **nada** do que
o autor escreve chega a ser HTML.

A ordem das operacoes e a defesa inteira, e por isso esta escrita aqui:

1. **Escapa-se tudo primeiro.** `html.escape` corre sobre o texto completo antes
   de qualquer regra de marcacao. A partir deste ponto nao existe um `<` no
   texto: um `<script>` escrito pelo autor ja e `&lt;script&gt;` e nunca volta a
   ser uma etiqueta.
2. **A marcacao e aplicada sobre o texto ja escapado.** Os unicos `<` do
   resultado sao os que este ficheiro escreve, com nomes de etiqueta fixos.
3. **Os enderecos sao validados por lista de permissao, na forma decodificada.**
   Tem de comecar por `https://`, `http://` ou `/`, e sem espacos nem aspas.
   A verificacao desfaz o escape primeiro, porque e a forma decodificada que o
   browser vai navegar - validar a outra deixava passar `&#106;avascript:`.

Imagens e videos so podem vir **desta maquina** (`/media/`, `/estatico/`). Uma
imagem alojada fora seria um pedido do browser do aluno a um servidor de
terceiros cada vez que abrisse a newsletter - ou seja, o endereco IP da turma
entregue a alguem, exatamente aquilo que o resto do projeto evita. Ligacoes
para fora sao outra coisa e essas valem: um `[texto](url)` leva ao Moodle, e e
o aluno que decide clicar.
"""

import html
import re

# Prefixos aceitos numa ligacao, e nada de espacos, aspas ou sinais de menor.
_LIGACAO_BOA = re.compile(r"^(?:https?://|/)[^\s\"'<>\\]*$", re.IGNORECASE)
# Media: so daqui de dentro. A barra inicial e obrigatoria.
_MEDIA_BOA = re.compile(r"^/(?:media|estatico)/[A-Za-z0-9._\-]+$")

_IMAGEM = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)\)")
_VIDEO = re.compile(r"^!video\(([^)\s]+)\)$")
_LIGACAO = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_NEGRITO = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALICO = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_CODIGO = re.compile(r"`([^`\n]+)`")
_ITEM_LISTA = re.compile(r"^[-*]\s+(.*)$")
_ITEM_NUMERO = re.compile(r"^\d+[.)]\s+(.*)$")
_TITULO = re.compile(r"^(#{2,3})\s+(.*)$")
_CITACAO = re.compile(r"^(?:&gt;|>)\s?(.*)$")

# Um corpo maior do que isto nao e um post, e um ficheiro colado por engano.
LIMITE_CORPO = 20000


def _decodificado(endereco: str) -> str:
    """O endereco tal como o browser o vai ver.

    O texto chega aqui ja escapado - e essa a defesa principal - portanto um `&`
    do autor e neste ponto `&amp;`, e o browser volta a decodifica-lo quando le o
    atributo. Validar a forma escapada seria validar uma coisa e navegar outra:
    `&#106;avascript:` passaria por nao parecer `javascript:`. Desfaz-se o escape
    para a verificacao e mantem-se a forma escapada no atributo, que e a que tem
    de estar la.
    """
    return html.unescape(endereco)


def _ligacao_valida(endereco: str) -> bool:
    real = _decodificado(endereco)
    return bool(_LIGACAO_BOA.match(real)) and "javascript" not in real.lower()


def _media_valida(endereco: str) -> bool:
    return bool(_MEDIA_BOA.match(_decodificado(endereco)))


def _inline(texto: str) -> str:
    """Marcacao dentro de uma linha. Recebe texto JA escapado."""

    def imagem(achado: re.Match) -> str:
        alt, endereco = achado.group(1), achado.group(2)
        if not _media_valida(endereco):
            return f"[imagem recusada: {alt or endereco}]"
        return f'<img class="nl-img" src="{endereco}" alt="{alt}" loading="lazy">'

    def ligacao(achado: re.Match) -> str:
        rotulo, endereco = achado.group(1), achado.group(2)
        if not _ligacao_valida(endereco):
            return rotulo
        # `noopener` porque abre noutro separador: sem ele a pagina de destino
        # ganha uma referencia a esta e pode navega-la.
        fora = "" if endereco.startswith("/") else ' target="_blank" rel="noopener noreferrer"'
        return f'<a href="{endereco}"{fora}>{rotulo}</a>'

    # A imagem primeiro: `![x](y)` tambem casa com o padrao da ligacao, e se a
    # ligacao corresse antes ficava um `!` solto a frente de um `<a>`.
    texto = _IMAGEM.sub(imagem, texto)
    texto = _LIGACAO.sub(ligacao, texto)
    texto = _CODIGO.sub(r"<code>\1</code>", texto)
    texto = _NEGRITO.sub(r"<strong>\1</strong>", texto)
    texto = _ITALICO.sub(r"<em>\1</em>", texto)
    return texto


def para_html(corpo: str) -> str:
    """O corpo de um post em HTML seguro.

    Tudo o que sai daqui foi escapado antes de ser interpretado, e as unicas
    etiquetas presentes sao as que este ficheiro escreve.
    """
    if not corpo:
        return ""
    escapado = html.escape(corpo[:LIMITE_CORPO], quote=True)
    linhas = escapado.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    partes: list[str] = []
    paragrafo: list[str] = []
    lista: list[str] = []
    tipo_lista = ""
    citacao: list[str] = []

    def fechar_paragrafo() -> None:
        if paragrafo:
            partes.append(f'<p>{_inline(" ".join(paragrafo))}</p>')
            paragrafo.clear()

    def fechar_lista() -> None:
        nonlocal tipo_lista
        if lista:
            itens = "".join(f"<li>{_inline(i)}</li>" for i in lista)
            partes.append(f"<{tipo_lista}>{itens}</{tipo_lista}>")
            lista.clear()
            tipo_lista = ""

    def fechar_citacao() -> None:
        if citacao:
            partes.append(f'<blockquote>{_inline(" ".join(citacao))}</blockquote>')
            citacao.clear()

    def fechar_tudo() -> None:
        fechar_paragrafo()
        fechar_lista()
        fechar_citacao()

    for linha in linhas:
        despida = linha.strip()

        if not despida:
            fechar_tudo()
            continue

        video = _VIDEO.match(despida)
        if video:
            fechar_tudo()
            endereco = video.group(1)
            if _media_valida(endereco):
                partes.append(
                    '<video class="nl-video" controls preload="metadata" '
                    f'src="{endereco}"></video>'
                )
            else:
                partes.append("<p>[vídeo recusado]</p>")
            continue

        # Uma imagem sozinha na linha e uma figura, nao texto com uma imagem no
        # meio: ganha a largura toda em vez de ficar presa a altura da linha.
        so_imagem = _IMAGEM.fullmatch(despida)
        if so_imagem:
            fechar_tudo()
            partes.append(f'<figure>{_inline(despida)}</figure>')
            continue

        if despida in ("---", "***", "___"):
            fechar_tudo()
            partes.append('<hr class="nl-linha">')
            continue

        titulo = _TITULO.match(despida)
        if titulo:
            fechar_tudo()
            nivel = 2 if len(titulo.group(1)) == 2 else 3
            partes.append(
                f'<h{nivel} class="nl-titulo">{_inline(titulo.group(2))}</h{nivel}>'
            )
            continue

        cit = _CITACAO.match(despida)
        if cit:
            fechar_paragrafo()
            fechar_lista()
            citacao.append(cit.group(1))
            continue

        item = _ITEM_LISTA.match(despida)
        if item:
            fechar_paragrafo()
            fechar_citacao()
            if tipo_lista and tipo_lista != "ul":
                fechar_lista()
            tipo_lista = "ul"
            lista.append(item.group(1))
            continue

        numerado = _ITEM_NUMERO.match(despida)
        if numerado:
            fechar_paragrafo()
            fechar_citacao()
            if tipo_lista and tipo_lista != "ol":
                fechar_lista()
            tipo_lista = "ol"
            lista.append(numerado.group(1))
            continue

        fechar_lista()
        fechar_citacao()
        paragrafo.append(despida)

    fechar_tudo()
    return "".join(partes)


def resumir(corpo: str, limite: int = 180) -> str:
    """Texto simples, sem marcacao, para a lista de posts e para o aviso.

    Nao chama `para_html`: o resumo aparece dentro de atributos e de linhas
    curtas, e o que se quer aqui e a frase, nao a formatacao.
    """
    limpo = _IMAGEM.sub("", corpo or "")
    limpo = _VIDEO.sub("", limpo)
    limpo = _LIGACAO.sub(r"\1", limpo)
    # Marcadores de bloco: so contam no inicio da linha. Comer todos os hifenes
    # do texto transformava "pre-aula" em "pre aula" e "Fisica-Quimica" em duas
    # palavras - o resumo e para ser lido, nao so para caber.
    limpo = re.sub(r"(?m)^\s*(?:#{1,3}|&gt;|>|[-*]|\d+[.)])\s+", "", limpo)
    limpo = limpo.replace("**", "").replace("`", "")
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 1].rsplit(" ", 1)[0] + "…"
