import html
import mimetypes
import time
import zipfile
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from app.analytics import uso
from app.indexing import storage
from app.models import newsletter, novidades
from app.interface import auth, disciplina as pagina_disciplina, estatisticas, protecao
from app.interface import estilo, icones, movimento, paginacao, som
from app.interface import marcacao, media, operacoes, painel, presenca
from app.interface import registo as registo_servidor
from app.interface.preview import fragmento, resolver_origem
from app.indexing.tokenizer import tokenizar
import json

from app.search import sugestoes
from app.search import seccoes as mod_seccoes
from app.search import hibrida
from app.search.query import MODO_OU, MODO_QUORUM
from app.search.snippet import gerar_trecho

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
RAIZ_DADOS = (Path("data") / "raw").resolve()
RAIZ_MARCA = (Path("assets") / "marca").resolve()
RAIZ_JS = (Path("assets") / "js").resolve()
RAIZ_FONTES = (Path("assets") / "fontes").resolve()
RAIZ_DOCS = (Path("assets") / "documentos").resolve()
# Nome do ficheiro -> (pasta, tipo). Lista fechada: o nome vem do endereco,
# portanto vem de fora, e comparar contra uma lista e mais simples de ler - e
# de confiar - do que tentar limpar ".." de um caminho.
_ESTATICOS = {
    "gato.png": (RAIZ_MARCA, "image/png"),
    "lettering.png": (RAIZ_MARCA, "image/png"),
    "icone.png": (RAIZ_MARCA, "image/png"),
    "404.png": (RAIZ_MARCA, "image/png"),
    "gato-fundo.png": (RAIZ_MARCA, "image/png"),
    "anime.min.js": (RAIZ_JS, "application/javascript; charset=utf-8"),
    "manrope.woff2": (RAIZ_FONTES, "font/woff2"),
    "libre-bodoni.woff2": (RAIZ_FONTES, "font/woff2"),
    "dm-mono-400.woff2": (RAIZ_FONTES, "font/woff2"),
    "dm-mono-500.woff2": (RAIZ_FONTES, "font/woff2"),
    "manual-utilizador.pdf": (RAIZ_DOCS, "application/pdf"),
    "politica-privacidade.pdf": (RAIZ_DOCS, "application/pdf"),
    "termos-de-uso.pdf": (RAIZ_DOCS, "application/pdf"),
    "pedido-remocao.pdf": (RAIZ_DOCS, "application/pdf"),
}
# Quantos resultados por pagina. Dez e o que um buscador mostra e o que
# torna a paginacao util: com vinte, quase nenhuma busca tinha pagina 2.
POR_PAGINA = paginacao.POR_PAGINA

_GUIAO = """
(function () {
  var painel = document.getElementById("painel");
  var campo = document.querySelector("input[name=q]");
  var consulta = campo ? campo.value : "";
  var cache = {};
  var relogio = null;

  function pedir(id, aoChegar) {
    if (cache[id] !== undefined) { aoChegar(cache[id]); return; }
    fetch("/preview?id=" + id + "&q=" + encodeURIComponent(consulta))
      .then(function (r) { return r.ok ? r.text() : ""; })
      .then(function (texto) { cache[id] = texto; aoChegar(texto); })
      .catch(function () { cache[id] = ""; });
  }

  function mostrar(item, texto) {
    if (!texto) { return; }
    painel.innerHTML = texto;
    painel.style.display = "block";
    var caixa = item.getBoundingClientRect();
    var limite = window.innerHeight - painel.offsetHeight - 12;
    painel.style.top = Math.max(12, Math.min(caixa.top, limite)) + "px";
  }

  (function () {
    var caixa = document.getElementById("sugestoes");
    if (!campo || !caixa) { return; }
    var envolve = campo.closest(".campo");
    var lista = [];
    var ativa = -1;
    var espera = null;
    var ultimoPedido = "";

    function fechar() {
      caixa.style.display = "none";
      if (envolve) { envolve.classList.remove("aberto"); }
      ativa = -1;
    }

    function marcar() {
      var filhos = caixa.children;
      for (var i = 0; i < filhos.length; i++) {
        filhos[i].className = i === ativa ? "ativa" : "";
      }
    }

    function escolher(texto) {
      campo.value = texto;
      fechar();
      campo.form.submit();
    }

    function desenhar(itens) {
      caixa.innerHTML = "";
      if (!itens.length) { fechar(); return; }
      itens.forEach(function (item) {
        var linha = document.createElement("div");
        var texto = document.createElement("span");
        texto.textContent = item.texto;
        var fonte = document.createElement("span");
        fonte.className = "fonte";
        fonte.textContent = item.origem === "historico" ? "ja pesquisou"
          : item.origem === "popular" ? "popular" : "";
        linha.appendChild(texto);
        linha.appendChild(fonte);
        linha.addEventListener("mousedown", function (e) {
          e.preventDefault();
          escolher(item.texto);
        });
        caixa.appendChild(linha);
      });
      lista = itens;
      ativa = -1;
      caixa.style.display = "block";
      if (envolve) { envolve.classList.add("aberto"); }
    }

    function pedirSugestoes() {
      var termo = campo.value.trim();
      if (termo.length < 2 || termo === ultimoPedido) {
        if (termo.length < 2) { fechar(); }
        return;
      }
      ultimoPedido = termo;
      fetch("/sugerir?q=" + encodeURIComponent(termo))
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(desenhar)
        .catch(fechar);
    }

    campo.addEventListener("input", function () {
      clearTimeout(espera);
      espera = setTimeout(pedirSugestoes, 160);
    });

    campo.addEventListener("keydown", function (e) {
      if (caixa.style.display !== "block") { return; }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        ativa = (ativa + 1) % lista.length;
        marcar();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        ativa = ativa <= 0 ? lista.length - 1 : ativa - 1;
        marcar();
      } else if (e.key === "Enter" && ativa >= 0) {
        e.preventDefault();
        escolher(lista[ativa].texto);
      } else if (e.key === "Escape") {
        fechar();
      }
    });

    campo.addEventListener("blur", function () { setTimeout(fechar, 120); });
  })();

  if (!painel) { return; }
  Array.prototype.forEach.call(
    document.querySelectorAll(".resultado"),
    function (item) {
      var id = item.getAttribute("data-id");

      item.addEventListener("mouseenter", function () {
        if (window.innerWidth <= 1024) { return; }
        relogio = setTimeout(function () {
          pedir(id, function (texto) { mostrar(item, texto); });
        }, 350);
      });
      item.addEventListener("mouseleave", function () {
        clearTimeout(relogio);
        painel.style.display = "none";
      });

      var botao = item.querySelector(".prever");
      var destino = item.querySelector(".pv-inline");
      if (botao && destino) {
        botao.addEventListener("click", function () {
          if (destino.innerHTML) {
            destino.innerHTML = "";
            botao.textContent = "prever";
            return;
          }
          pedir(id, function (texto) {
            destino.innerHTML = texto;
            botao.textContent = "fechar";
          });
        });
      }
    }
  );
})();
"""


# Desenhada aqui e nao com um caracter tipografico: os simbolos de lupa do
# Unicode ou nao existem em metade das fontes ou sao emojis a cores.
_LUPA = (
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" '
    'stroke="currentColor" stroke-width="2" aria-hidden="true">'
    '<circle cx="10.5" cy="10.5" r="6.5"></circle>'
    '<path d="M15.5 15.5 L21 21"></path></svg>'
)


def _caixa_busca(consulta: str, opcoes: str = "", autofoco: bool = False,
                 rotulo: str = "", disciplina: str = "") -> str:
    """A caixa de pesquisa. A mesma no topo dos resultados e no heroi.

    Com `opcoes` desenha o seletor de disciplina; sem elas, leva a disciplina
    num campo escondido. E o que faz o cabecalho dos resultados nao repetir o
    filtro que ja esta na coluna da esquerda - no telemovel os dois ficavam um
    por cima do outro e pareciam avaria - sem que pesquisar de novo perca a
    disciplina que o aluno tinha escolhido.
    """
    foco = " autofocus" if autofoco else ""
    marcador = rotulo or "Procurar no material da escola"
    if opcoes:
        filtro = (
            f'<span class="filtro"><select name="d" aria-label="disciplina">'
            f"{opcoes}</select></span>"
        )
    elif disciplina:
        filtro = (
            f'<input type="hidden" name="d" '
            f'value="{html.escape(disciplina, quote=True)}">'
        )
    else:
        filtro = ""
    return (
        '<form class="busca" action="/" method="get">'
        '<span class="campo">'
        f'<span class="ic-lupa">{icones.svg("lupa", 16)}</span>'
        f'<input type="text" name="q" value="{consulta}"{foco} autocomplete="off" '
        f'placeholder="{marcador}" aria-label="o que procura">'
        '<div id="sugestoes"></div></span>'
        f"{filtro}"
        '<button class="botao-solido quadrado" type="submit" '
        f'aria-label="pesquisar">{icones.svg("seta-dir", 17)}</button>'
        "</form>"
    )


def _pagina(consulta: str, opcoes: str, novidades: str, corpo: str,
            abas: str = "", pagina: str = "busca", disciplina: str = "",
            administrador: bool = False) -> str:
    """O esqueleto das paginas com cabecalho.

    `administrador` decide se o cabecalho mostra a entrada para o painel.
    Mostrar um botao que devolve 403 ensinava o aluno a bater numa porta
    fechada, e fazia a interface parecer avariada estando a funcionar bem.
    """
    return (
        f"{estilo.cabeca('Madalena')}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{_caixa_busca(consulta, disciplina=disciplina)}"
        f"{estilo.acoes(pagina, administrador)}"
        "</div></header>\n"
        f"{corpo}\n"
        f"{estilo.rodape()}\n"
        '<div id="painel"></div>\n'
        f"<script>{_GUIAO}{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}{som.marcacao()}\n"
        "</body>\n</html>"
    )


def _pagina_entrada(erro: str = "") -> bytes:
    """A porta de entrada dos alunos que estao a testar.

    Uma folha inteira: marca em cima, titulo grande ao centro, o campo do
    codigo entre duas linhas, e tres marcas monoespacadas em baixo. Sem
    cabecalho de navegacao - quem chega aqui ou tem codigo ou nao tem.
    """
    classe = " errado" if erro else ""
    dica = (
        f'<p class="dica erro" aria-live="polite">{html.escape(erro)}</p>'
        if erro
        else '<p class="dica" aria-live="polite">O código é fornecido pelo '
             "responsável do projeto.</p>"
    )
    corpo = (
        f"{estilo.cabeca('Madalena - entrar')}\n"
        "<body>\n"
        '<div class="folha">'
        '<div class="folha-topo">'
        f"{estilo.marca()}"
        '<div class="direita">'
        '<span class="olho">acesso restrito</span>'
        f"{som.botao()}{estilo.botao_tema()}"
        "</div></div>\n"
        '<div class="folha-meio"><div class="entrada-caixa">'
        '<p class="olho">Madalena Search</p>'
        '<h1 class="display h-gigante">Acesso ao \u00edndice.</h1>'
        '<p class="lead">Introduz o c\u00f3digo da tua turma para pesquisar '
        "o material escolar.</p>"
        '<form class="entrada-forma" method="post" action="/entrar">'
        '<label class="olho" for="codigo">C\u00f3digo de acesso</label>'
        '<div class="entrada-linha">'
        f'<input class="codigo{classe}" id="codigo" type="text" name="codigo" '
        'placeholder="EX.: MADA-24" autofocus autocomplete="off">'
        '<button class="botao-solido" type="submit">Entrar'
        f'{icones.svg("seta-dir", 16)}</button>'
        "</div>"
        f"{dica}"
        "</form>"
        '<p class="nota-final">Projeto em fase de teste, restrito a '
        "participantes convidados. Fica registado <b>o que escreves na caixa "
        "de busca</b>, a data e o documento que abres, ligados ao teu r\u00f3tulo "
        "(aluno-01, aluno-02...) e nao ao teu nome. O endere\u00e7o IP <b>nao</b> "
        "\u00e9 guardado. Tudo \u00e9 apagado ao fim de 90 dias, e podes pedir para "
        "apagar antes disso. Nao partilhes o teu c\u00f3digo. "
        '<a href="/privacidade">Como os teus dados s\u00e3o tratados</a>.</p>'
        "</div></div>\n"
        '<div class="folha-rodape">'
        "<span>\u00cdndice local</span>"
        "<span>Sem servi\u00e7os externos</span>"
        '<span><a href="/privacidade">Os teus dados</a></span>'
        f"{estilo.credito()}"
        "</div>"
        "</div>\n"
        f"<script>{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}{som.marcacao()}\n"
        "</body>\n</html>"
    )
    return corpo.encode("utf-8")


def _ler_arquivo(origem: str) -> tuple[bytes, str]:
    caminho, interno, _, _ = resolver_origem(origem)
    resolvido = caminho.resolve()
    if not resolvido.is_relative_to(RAIZ_DADOS):
        raise PermissionError("fora da raiz de dados")
    if interno:
        with zipfile.ZipFile(resolvido) as arquivo_zip:
            return arquivo_zip.read(interno), Path(interno).name
    return resolvido.read_bytes(), resolvido.name


def _ligacao(doc, consulta: str = "", posicao: int | None = None) -> str:
    parametros = {"id": str(doc.id)}
    if consulta:
        parametros["q"] = consulta
    if posicao:
        parametros["p"] = str(posicao)
    if doc.origem.startswith(("http://", "https://")):
        return "/abrir?" + urlencode(parametros)
    _, _, pagina, _ = resolver_origem(doc.origem)
    if consulta:
        parametros["q"] = consulta
    if posicao:
        parametros["p"] = str(posicao)
    url = "/documento?" + urlencode(parametros)
    if pagina:
        url += f"#page={pagina}"
    return url


def _opcoes(disciplinas: list[str], selecionada: str) -> str:
    partes = ['<option value="">todas as disciplinas</option>']
    for nome in disciplinas:
        marca = " selected" if nome == selecionada else ""
        seguro = html.escape(nome)
        partes.append(f'<option value="{seguro}"{marca}>{seguro}</option>')
    return "".join(partes)


def _destacar(trecho: str, termos: set[str]) -> str:
    partes = []
    for palavra in trecho.split(" "):
        segura = html.escape(palavra)
        normalizada = tokenizar(palavra, remover_stop_words=False)
        if normalizada and normalizada[0] in termos:
            partes.append(f"<b>{segura}</b>")
        else:
            partes.append(segura)
    return " ".join(partes)


def _bloco_correcao(resultado, consulta: str, disciplina: str) -> str:
    if not resultado.correcao:
        return ""
    aplicada = resultado.consulta_aplicada(consulta)
    original = "/?" + urlencode(
        {"q": consulta, "d": disciplina, "exato": "1"}
    )
    return (
        '<p class="sugestao">A mostrar resultados para '
        f"<b>{html.escape(aplicada)}</b> &middot; "
        f'<a href="{html.escape(original)}">pesquisar antes por '
        f"{html.escape(consulta)}</a></p>"
    )


def _bloco_sugestao(resultado, consulta: str, disciplina: str) -> str:
    if not resultado.sugestoes:
        return ""
    corrigida = resultado.consulta_corrigida(consulta)
    if corrigida.lower() == consulta.lower():
        return ""
    destino = "/?" + urlencode({"q": corrigida, "d": disciplina, "corrigida": "1"})
    return (
        '<p class="sugestao">Será que quis dizer: '
        f'<a href="{html.escape(destino)}">{html.escape(corrigida)}</a>?</p>'
    )


def _renderizar(
    consulta: str, disciplina: str, resultado, seccao: str = "",
    mostrar_pontuacao: bool = False, pagina: int = 1, segundos: float = 0.0,
    opcoes: str = "",
) -> str:
    """A pagina de resultados inteira: coluna de filtros a esquerda, lista a direita."""
    sugestao = _bloco_correcao(resultado, consulta, disciplina) + _bloco_sugestao(
        resultado, consulta, disciplina
    )
    if not resultado.documentos:
        return (
            '<div class="envolve"><div class="grelha-busca">'
            f"{_lado(opcoes, consulta, seccao)}"
            "<div>"
            f"{sugestao}"
            '<div class="nada">'
            '<p class="display h-grande">Nada por aqui.</p>'
            '<p class="lead">Tenta outra palavra, ou tira algum filtro.</p>'
            "</div></div></div></div>"
        )

    termos = set(tokenizar(consulta))
    if resultado.modo == MODO_QUORUM:
        aviso = (
            f" &middot; nenhum documento tem os {resultado.termos_totais} termos;"
            f" a mostrar os que tem pelo menos {resultado.termos_exigidos}"
        )
    elif resultado.modo == MODO_OU:
        aviso = " &middot; a mostrar documentos com algum dos termos"
    else:
        aviso = ""

    paginas = {
        grupo.documento.id: grupo.paginas for grupo in getattr(resultado, "grupos", [])
    }
    grupos = mod_seccoes.agrupar(resultado.documentos)
    escolhidos = (
        mod_seccoes.filtrar(resultado.documentos, seccao)
        if seccao
        else resultado.documentos
    )
    janela = paginacao.calcular(len(escolhidos), pagina)

    return (
        '<div class="envolve"><div class="grelha-busca">'
        f"{_lado(opcoes, consulta, seccao)}"
        "<div>"
        f'<p class="olho">{_contagem(len(escolhidos))} para '
        f"&ldquo;{html.escape(consulta)}&rdquo;{_tempo(segundos)}{aviso}</p>"
        f"{_abas(resultado.documentos, grupos, consulta, disciplina, seccao)}"
        f"{sugestao}"
        f"{_corpo_resultados(escolhidos, consulta, disciplina, termos, seccao, paginas, mostrar_pontuacao, janela)}"
        f"{_barra_paginas(janela, consulta, disciplina, seccao)}"
        "</div></div></div>"
    )


def _lado(opcoes: str, consulta: str = "", seccao: str = "") -> str:
    """A coluna de filtros. No telemovel encolhe para uma linha so (ver CSS).

    O `select` leva um formulario proprio a volta e nao so o `onchange`: sem
    formulario, mudar de disciplina nao fazia nada - o controlo parecia vivo e
    era um adorno. Com o formulario funciona tambem sem JavaScript, porque o
    botao de reserva submete-o.
    """
    escondidos = f'<input type="hidden" name="q" value="{html.escape(consulta, quote=True)}">'
    if seccao:
        escondidos += f'<input type="hidden" name="s" value="{html.escape(seccao, quote=True)}">'
    return (
        '<aside class="lado">'
        '<p class="olho">Filtrar resultados</p>'
        '<form class="lado-bloco" action="/" method="get">'
        f"{escondidos}"
        '<label for="d-lado">Disciplina</label>'
        '<select id="d-lado" name="d" onchange="this.form.submit()">'
        f"{opcoes}</select>"
        '<noscript><button class="botao-solido" type="submit">aplicar</button></noscript>'
        "</form>"
        "</aside>"
    )


def _abas(documentos, grupos, consulta: str, disciplina: str, seccao: str) -> str:
    """As seccoes viraram separadores, no lugar onde o Google poe os dele.

    Antes, cada seccao mostrava cinco resultados e um "ver os N" ao lado. Isso
    nao se paginava: a pagina 2 de um ecra com quatro listas de cinco nao quer
    dizer nada. Como separadores, cada vista e uma lista corrida - e uma lista
    corrida pagina-se.
    """
    if len(grupos) <= 1:
        return ""
    itens = [("", "Tudo", len(documentos))]
    itens += [(grupo.chave, grupo.titulo, len(lista)) for grupo, lista in grupos]
    partes = []
    for chave, titulo, quantos in itens:
        ativa = " ativa" if chave == seccao else ""
        destino = html.escape(_url(consulta, disciplina, chave))
        partes.append(
            f'<a class="aba{ativa}" href="{destino}">{html.escape(titulo)}'
            f'<span class="conta">{quantos}</span></a>'
        )
    return f'<nav class="abas">{"".join(partes)}</nav>'


def _barra_paginas(janela, consulta: str, disciplina: str, seccao: str) -> str:
    """A barra de paginas, no feitio a que toda a gente ja esta habituada."""
    if janela.total_paginas <= 1:
        return ""
    base = {"q": consulta, "d": disciplina, "s": seccao}
    partes = []
    if janela.ha_anterior:
        destino = html.escape(paginacao.url(base, janela.pagina - 1))
        partes.append(
            f'<a class="salto" href="{destino}">'
            f'{icones.svg("seta-esq", 15)}anterior</a>'
        )
    for numero in paginacao.numeros(janela):
        if numero == janela.pagina:
            partes.append(f'<span class="atual">{numero}</span>')
        else:
            destino = html.escape(paginacao.url(base, numero))
            partes.append(f'<a href="{destino}">{numero}</a>')
    if janela.ha_seguinte:
        destino = html.escape(paginacao.url(base, janela.pagina + 1))
        partes.append(
            f'<a class="salto" href="{destino}">seguinte'
            f'{icones.svg("seta-dir", 15)}</a>'
        )
    resumo = (
        f'<span class="resumo">resultados {janela.inicio + 1} a {janela.fim} '
        f"de {janela.total_itens} &middot; página {janela.pagina} "
        f"de {janela.total_paginas}</span>"
    )
    return f'<nav class="paginacao">{"".join(partes)}{resumo}</nav>'


_MESES = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)


def _data_legivel(iso: str) -> str:
    """"2026-07-24" -> "jul 2026".

    O dia exato nao interessa; o mes e o ano dizem se o material e deste
    periodo ou do ano passado. Serve tambem para distinguir ficheiros com o
    mesmo nome: ha quatro "FichaRevisoes.pdf", um por modulo, e ate agora
    apareciam na lista como quatro linhas iguais.
    """
    partes = (iso or "").split("-")
    if len(partes) < 2 or not partes[0].isdigit() or not partes[1].isdigit():
        return ""
    mes = int(partes[1])
    if not 1 <= mes <= 12:
        return ""
    return f"{_MESES[mes - 1]} {partes[0]}"


def _outras_paginas(quantas: int) -> str:
    """Diz que o mesmo ficheiro tem mais paginas com a consulta.

    Antes, cada pagina era um resultado: "regulamento interno" enchia os dez
    lugares com o mesmo PDF. Agora o ficheiro aparece uma vez, pela melhor
    pagina, e o resto conta-se aqui.
    """
    if quantas <= 1:
        return ""
    outras = quantas - 1
    palavra = "página" if outras == 1 else "páginas"
    return f'<p class="paginas">e mais {outras} {palavra} neste documento</p>'


def _fonte_legivel(origem: str) -> str:
    """De onde vem o documento, na linha por cima do titulo.

    E o lugar onde o Google poe o endereco do sitio. Para o material do
    Moodle e do site da escola, o anfitriao diz mesmo alguma coisa; para um
    ficheiro que foi descarregado a mao, dizer o caminho em disco nao ajuda
    ninguem e ainda revela a arrumacao da maquina.
    """
    if origem.startswith(("http://", "https://")):
        return urlparse(origem).netloc.removeprefix("www.")
    return "ficheiro"


def _um_resultado(
    doc, pontuacao, consulta, posicao, termos, paginas=1,
    mostrar_pontuacao=False, mostrar_disciplina=True,
):
    trecho = _destacar(gerar_trecho(doc.texto, termos), termos)

    origem = [f'<span>{html.escape(_tipo_legivel(doc))}</span>']
    if doc.disciplina and mostrar_disciplina:
        origem.append('<span class="ponto"></span>')
        origem.append(f"<span>{html.escape(doc.disciplina)}</span>")
    quando = _data_legivel(getattr(doc, "data", ""))
    if quando:
        origem.append('<span class="ponto"></span>')
        origem.append(f"<span>{quando}</span>")

    # A pontuacao e um numero de depuracao. Nao diz nada a um aluno e, no
    # telemovel, empurrava metade do titulo para a linha seguinte. Fica para
    # quem afina o ranqueamento.
    pontos = (
        f'<span class="pontuacao">{pontuacao:.4f}</span>'
        if mostrar_pontuacao
        else ""
    )
    return (
        f'<article class="resultado" data-id="{doc.id}">'
        f'<div class="linha-origem">{"".join(origem)}</div>'
        f'<h3 class="titulo">'
        f'<a href="{html.escape(_ligacao(doc, consulta, posicao))}"'
        ' target="_blank" rel="noopener">'
        f'{html.escape(doc.titulo)}{icones.svg("fora", 13)}</a>'
        f"{pontos}</h3>"
        f'<p class="trecho">{trecho}</p>'
        f"{_outras_paginas(paginas)}"
        '<button type="button" class="prever">'
        f'{icones.svg("olho", 14)}prever</button>'
        '<div class="pv-inline"></div>'
        "</article>"
    )


def _tipo_legivel(doc) -> str:
    """A primeira etiqueta da linha de origem: que especie de documento e."""
    return mod_seccoes.titulo_da(mod_seccoes.classificar(doc)) or "Documento"


def _url(consulta, disciplina, seccao=""):
    """Endereco da mesma busca noutra seccao. Mudar de seccao volta a pagina 1."""
    parametros = {"q": consulta}
    if disciplina:
        parametros["d"] = disciplina
    if seccao:
        parametros["s"] = seccao
    return "/?" + urlencode(parametros)


def _tempo(segundos: float) -> str:
    """O tempo que a busca levou, como se ve em qualquer motor de busca.

    Mede so a busca, nao a montagem do HTML nem a viagem pela rede - e o
    numero que diz alguma coisa sobre o indice. Virgula decimal, que e como
    se escreve em portugues.
    """
    if segundos <= 0:
        return ""
    return f" ({segundos:.2f} segundos)".replace(".", ",")


def _contagem(quantos: int) -> str:
    """"1 resultado", "32 resultados". O "(s)" e escrita de programador."""
    if quantos == 1:
        return "1 resultado"
    return f"{quantos} resultados"


def _distingue_disciplina(itens) -> bool:
    """So vale a pena a etiqueta se as disciplinas nao forem todas iguais.

    Numa busca por criterios, os cinco primeiros diziam todos "Escola": cinco
    etiquetas a ocupar espaco sem separar nada.
    """
    vistas = {doc.disciplina for doc, _ in itens if doc.disciplina}
    return len(vistas) > 1


def _corpo_resultados(
    documentos, consulta, disciplina, termos, seccao, paginas=None,
    mostrar_pontuacao=False, janela=None,
):
    """A lista corrida de resultados da pagina pedida.

    Deixou de decidir seccoes: isso e das abas, la em cima. Aqui so se corta
    a janela e se desenham as linhas.
    """
    # {id do documento: quantas paginas do mesmo ficheiro casaram}
    paginas = paginas or {}
    if janela is None:
        janela = paginacao.calcular(len(documentos), 1)
    visiveis = janela.fatiar(documentos)
    mostra_disciplina = _distingue_disciplina(visiveis)
    return "\n".join(
        _um_resultado(
            doc, pontuacao, consulta, janela.inicio + posicao, termos,
            paginas.get(doc.id, 1), mostrar_pontuacao, mostra_disciplina,
        )
        for posicao, (doc, pontuacao) in enumerate(visiveis, start=1)
    )


# Tres buscas que a turma faz mesmo, tiradas do registo de uso.
_EXEMPLOS = ("horários", "critérios de avaliação", "regulamento")


def _pagina_inicial(opcoes: str, administrador: bool = False) -> str:
    """O heroi: titulo grande, a barra, e tres buscas para experimentar."""
    exemplos = "".join(
        f'<a href="/?{urlencode({"q": termo})}">{html.escape(termo)}</a>'
        for termo in _EXEMPLOS
    )
    return (
        f"{estilo.cabeca('Madalena')}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{estilo.acoes('busca', administrador)}"
        "</div></header>\n"
        '<div class="envolve"><section class="heroi">'
        '<div class="heroi-gato" aria-hidden="true" '
        "style=\"background-image:url(/estatico/gato-fundo.png)\"></div>"
        '<div class="heroi-dentro">'
        '<p class="olho">Madalena / pesquisa escolar</p>'
        '<h1 class="display h-gigante">Encontra o que a escola j\u00e1 sabe.</h1>'
        '<p class="lead">Hor\u00e1rios, fichas, regulamentos e p\u00e1ginas do site '
        "&mdash; num s\u00f3 \u00edndice, feito para chegar depressa ao que importa.</p>"
        f"{_caixa_busca('', opcoes, autofoco=True, rotulo='O que procuras?')}"
        f'<div class="experimente"><span>Experimenta:</span>{exemplos}</div>'
        "</div></section></div>\n"
        f"{estilo.rodape()}\n"
        f"<script>{_GUIAO}{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}{som.marcacao()}\n"
        "</body>\n</html>"
    )


def _montar_pagina(
    consulta: str, disciplina: str, participante: str,
    corrigida: bool = False, seccao: str = "", exato: bool = False,
    pagina: int = 1,
) -> str:
    administrador = auth.e_administrador(participante)
    disciplinas: list[str] = []
    if not CAMINHO_BANCO.exists():
        corpo = (
            '<div class="envolve"><div class="nada">'
            '<p class="display h-grande">\u00cdndice n\u00e3o encontrado.</p>'
            '<p class="lead">Corre: python main.py indexar &lt;caminho&gt;</p>'
            "</div></div>"
        )
        return _pagina("", "", "", corpo, administrador=administrador)

    # A ligacao ao indice e uma so para o processo todo, e a tranca deixa
    # passar uma busca de cada vez. Parece o contrario do que se quer, mas foi
    # medido: com oito alunos em simultaneo, ligacao nova por pedido dava
    # 6.9 s e esta da 0.2 s. Ver storage.emprestada.
    resultado = None
    segundos = 0.0
    with storage.emprestada(CAMINHO_BANCO) as conexao:
        disciplinas = storage.listar_disciplinas(conexao)
        if not consulta and not disciplina:
            return _pagina_inicial(_opcoes(disciplinas, ""), administrador)
        if not consulta and disciplina:
            with uso.partilhada() as registo:
                corpo = pagina_disciplina.pagina(conexao, registo, disciplina)
            return _pagina(
                consulta="",
                opcoes=_opcoes(disciplinas, disciplina),
                novidades="",
                corpo=f'<div class="pagina-apoio">{corpo}</div>',
                administrador=administrador,
            )
        comeco = time.perf_counter()
        resultado = hibrida.buscar(
            conexao, consulta, disciplina=disciplina or None,
            permitir_ou=not exato,
        )
        segundos = time.perf_counter() - comeco
        # So a primeira pagina conta como busca. Sem isto, folhear ate a
        # pagina 5 registava cinco buscas iguais: a mesma pergunta passava a
        # parecer cinco vezes mais popular do que e, e o numero de buscas sem
        # resultado ficava dividido por quantas paginas o aluno virou.
        if pagina == 1:
            with uso.partilhada() as registo:
                uso.registar(
                    registo, participante, uso.EVENTO_BUSCA,
                    consulta=consulta,
                    disciplina=disciplina or None,
                    resultados=len(resultado.documentos),
                    modo=resultado.modo,
                )
                if corrigida:
                    uso.registar(
                        registo, participante, uso.EVENTO_SUGESTAO,
                        consulta=consulta,
                    )

    # Fora da tranca: montar o HTML sao dezena de milissegundos de Python que
    # nao tocam na base de dados, e segurar a fila com eles seria fazer os
    # outros alunos esperar por nada.
    opcoes = _opcoes(disciplinas, disciplina)
    corpo = _renderizar(
        consulta, disciplina, resultado, seccao,
        auth.e_administrador(participante), pagina, segundos, opcoes,
    )
    return _pagina(
        consulta=html.escape(consulta, quote=True),
        opcoes=opcoes,
        novidades="",
        corpo=corpo,
        disciplina=disciplina,
        administrador=administrador,
    )


def _aviso_novidades() -> str:
    """Uma linha discreta a dizer o que apareceu, se apareceu alguma coisa."""
    try:
        quantas = novidades.contar_recentes()
    except OSError:
        return ""
    if not quantas:
        return ""
    palavra = "documento novo" if quantas == 1 else "documentos novos"
    return (
        f'<p class="novo">{icones.svg("brilho", 16)}'
        f"{quantas} {palavra} nos últimos"
        f' {novidades.DIAS_RECENTES} dias &middot;'
        f' <a href="/novidades">ver quais</a></p>'
    )


def _disciplinas_disponiveis() -> list[str]:
    if not CAMINHO_BANCO.exists():
        return []
    with storage.emprestada(CAMINHO_BANCO) as conexao:
        return storage.listar_disciplinas(conexao)


# Os mesmos dois enderecos dos PDFs. O escolar vem primeiro: e institucional,
# e ninguem devia ter de escrever para um endereco pessoal para exercer um
# direito. Vivem aqui e em `scripts/gerar_documentos.py` - se mudarem, mudam
# nos dois sitios, e o script tem de correr outra vez.
CONTACTO_ESCOLAR = "a2025016@alunos.sefo.pt"
CONTACTO_PESSOAL = "eduardo.carvalho.pt.dev@gmail.com"

_DOCUMENTOS = (
    (
        "manual-utilizador.pdf",
        "Manual do utilizador",
        "Como procurar, como ler os resultados e como escrever melhor a "
        "pergunta. Com imagens de cada ecrã.",
    ),
    (
        "termos-de-uso.pdf",
        "Termos de uso",
        "O que é o Madalena, quem pode usá-lo, e o que não é garantido "
        "— disponibilidade, completude e atualidade.",
    ),
    (
        "politica-privacidade.pdf",
        "Política de Privacidade e Cookies",
        "O que fica registado quando pesquisas, porque fica, durante quanto "
        "tempo, e como pedir para apagar.",
    ),
    (
        "pedido-remocao.pdf",
        "Pedido de remoção do índice",
        "Para pedir que um documento deixe de aparecer nas pesquisas: dados "
        "pessoais, ficheiros internos ou direitos de autor.",
    ),
)


def _pagina_privacidade() -> str:
    """A pagina publica dos documentos.

    Vive fora da barreira de sessao. Quem precisa de saber o que e registado
    costuma ser exactamente quem ainda nao entrou - um encarregado de educacao
    a decidir se autoriza o filho a participar nao tem codigo nenhum.
    """
    linhas = []
    for ficheiro, titulo, descricao in _DOCUMENTOS:
        linhas.append(
            f'<li><a href="/estatico/{ficheiro}" target="_blank" rel="noopener">'
            f'{icones.svg("ficheiro", 15)}{html.escape(titulo)}</a>'
            f'<span class="quando">PDF</span>'
            f'<p class="doc-diz">{html.escape(descricao)}</p></li>'
        )
    return (
        '<div class="pagina-apoio">'
        f'<a class="voltar" href="/">{icones.svg("seta-esq", 14)}voltar \u00e0 busca</a>'
        '<p class="olho">Transpar\u00eancia</p>'
        '<h1 class="display h-grande">Os teus dados</h1>'
        '<div class="bloco-linhas">'
        '<p class="grande">Fica registado o que escreves na caixa de busca, a data, '
        "e o documento que abres.</p>"
        '<p class="pequena">Ligado ao teu r\u00f3tulo (aluno-01, aluno-02...) e n\u00e3o ao '
        "teu nome. O endere\u00e7o IP <b>n\u00e3o</b> \u00e9 guardado. Tudo \u00e9 apagado ao fim de "
        "90 dias.</p>"
        "</div>"
        f'<ul class="novo-lista lista-docs">{"".join(linhas)}</ul>'
        '<div class="bloco-linhas">'
        '<p class="grande">Queres ver, apagar ou opores-te ao registo?</p>'
        '<p class="pequena">Escreve para '
        f'<a href="mailto:{CONTACTO_ESCOLAR}">{CONTACTO_ESCOLAR}</a> ou '
        f'<a href="mailto:{CONTACTO_PESSOAL}">{CONTACTO_PESSOAL}</a>. '
        "N\u00e3o precisas de justificar, e a resposta chega em menos de 30 dias.</p>"
        "</div>"
        '<p class="lado-nota">Estes documentos descrevem um piloto escolar fechado. '
        "Se alguma coisa neles n\u00e3o corresponder ao que o sistema faz, o erro "
        "\u00e9 do documento e deve ser comunicado.</p>"
        "</div>"
    )


def _cartao_post(post) -> str:
    """Um post da newsletter como os alunos o veem.

    O corpo passa por `marcacao.para_html`, que escapa tudo antes de interpretar
    a marcacao - o texto foi escrito por uma pessoa e nunca chega a ser HTML.
    """
    retrato = media.perfil_de(post.autor)
    cara = (
        f'<img class="nl-retrato" src="/perfil/{html.escape(retrato, quote=True)}"'
        ' alt="">'
        if retrato
        else ""
    )
    rascunho = (
        '<span class="rascunho">rascunho</span>' if not post.publicado else ""
    )
    return (
        f'<article class="nl-post" id="post-{post.id}">'
        f'<p class="nl-meta">{cara}<span>{html.escape(post.data_curta)}</span>'
        f"<span>{html.escape(post.autor)}</span>{rascunho}</p>"
        f'<h2 class="nl-cabeca">{html.escape(post.titulo or "Sem título")}</h2>'
        f'<div class="nl-corpo">{marcacao.para_html(post.corpo)}</div>'
        "</article>"
    )


def _pagina_novidades(administrador: bool = False) -> str:
    """A newsletter em cima, o material novo do Moodle em baixo.

    Sao duas coisas diferentes na mesma pagina de proposito. O material novo e
    automatico - o que o conector encontrou. A newsletter e escrita: e onde cabe
    o "isto sai no teste" que nenhum ficheiro diz.
    """
    posts = newsletter.listar(so_publicados=True)
    bloco_posts = (
        "".join(_cartao_post(post) for post in posts)
        if posts
        else '<div class="bloco-linhas">'
        '<p class="grande">Ainda não há nada escrito aqui.</p>'
        '<p class="pequena">Quando houver, é o primeiro que se lê.</p>'
        "</div>"
    )

    recentes = novidades.recentes()
    if not recentes:
        bloco = (
            '<div class="bloco-linhas">'
            '<p class="grande">Ainda não chegou material novo nos últimos dias.</p>'
            '<p class="pequena">Quando chegar, aparece aqui.</p>'
            "</div>"
        )
    else:
        linhas = []
        for item in recentes:
            titulo = html.escape(item.titulo)
            disciplina = html.escape(item.disciplina)
            # Leva a busca ca dentro, nao ao Moodle: o url guardado e relativo
            # ao Moodle e resolveria contra o servidor errado.
            procura = urlencode({"q": item.titulo})
            linhas.append(
                f'<li><span class="disciplina">{disciplina}</span>'
                f'<a href="/?{procura}">{titulo}</a>'
                f'<span class="quando">{html.escape(item.data)}</span></li>'
            )
        bloco = f'<ul class="novo-lista">{"".join(linhas)}</ul>'

    escrever = (
        '<a class="pn-botao" href="/painel/newsletter">escrever um post</a>'
        if administrador
        else ""
    )
    return (
        '<div class="pagina-apoio">'
        f'<a class="voltar" href="/">{icones.svg("seta-esq", 14)}voltar à busca</a>'
        '<p class="olho">Newsletter</p>'
        '<h1 class="display h-grande">Novidades</h1>'
        f"{escrever}"
        f"{bloco_posts}"
        '<p class="olho" style="margin-top:64px">Do Moodle, automático</p>'
        '<h2 class="display h-grande" style="font-size:1.6rem;margin-top:8px">'
        "Material novo</h2>"
        f"{bloco}"
        "</div>"
    )


_limite_geral = protecao.Limitador(
    protecao.PEDIDOS_POR_MINUTO, protecao.JANELA_GERAL
)
_limite_entrada = protecao.Limitador(
    protecao.TENTATIVAS_ENTRADA, protecao.JANELA_ENTRADA
)


class _Servidor(ThreadingHTTPServer):
    # No Windows, allow_reuse_address permite que varios processos se liguem a
    # mesma porta em silencio - e o pedido acaba a ser servido por um processo
    # antigo, com codigo antigo. Preferimos falhar alto.
    allow_reuse_address = False
    daemon_threads = True


class _Manipulador(BaseHTTPRequestHandler):
    # Uma ligacao que nunca acaba de enviar prende uma thread para sempre.
    timeout = 20
    protocol_version = "HTTP/1.1"
    # Por omissao o cabecalho Server dizia "BaseHTTP/0.6 Python/3.11.15". A
    # versao exata do interpretador e meio caminho andado para quem procura
    # uma falha conhecida: nao ha razao para a oferecer.
    server_version = "Madalena"
    sys_version = ""

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (TimeoutError, ConnectionError, OSError):
            self.close_connection = True

    def _endereco(self) -> str:
        return protecao.endereco_do_pedido(self)

    def _excedeu_limite(self) -> bool:
        """Conta por participante quando ha sessao, por endereco quando nao ha.

        A turma inteira na rede da escola sai pelo mesmo IP publico. Contar so
        por endereco punia oito alunos a estudar como se fossem um bot: 120
        pedidos por minuto dividem-se depressa quando cada busca leva consigo
        sugestoes e pre-visualizacoes.

        Quem ainda nao entrou continua a ser contado por endereco - antes da
        sessao nao ha identidade nenhuma em que confiar, e e essa a porta que
        um ataque de forca bruta bate.
        """
        participante = self._participante()
        chave = f"p:{participante}" if participante else self._endereco()
        if _limite_geral.permitir(chave):
            return False
        self.send_error(429, "demasiados pedidos")
        return True

    def _participante(self) -> str | None:
        bruto = self.headers.get("Cookie")
        if not bruto:
            return None
        try:
            galletas = SimpleCookie(bruto)
        except Exception:
            return None
        item = galletas.get(auth.NOME_COOKIE)
        if item is None:
            return None
        return auth.participante_da_sessao(item.value, auth.segredo())

    def do_POST(self):
        try:
            self._tratar_post()
        except (TimeoutError, ConnectionError, BrokenPipeError):
            self.close_connection = True
        except Exception:
            registo_servidor.excecao(f"POST {self.path[:140]}", "http")
            try:
                self.send_error(500, "erro interno")
            except Exception:
                self.close_connection = True

    def _tratar_post(self):
        if self._excedeu_limite():
            return
        caminho = urlparse(self.path).path
        if caminho == "/entrar":
            self._entrar()
            return

        participante = self._participante()
        if participante is None or not auth.e_administrador(participante):
            # O mesmo 403 para quem nao entrou e para quem entrou sem ser
            # administrador, de proposito: a diferenca entre as duas respostas
            # dizia a quem sonda que o endereco existe e que faltava so o papel.
            self.send_error(403, "acesso restrito")
            return
        presenca.marcar(participante, self.headers.get("User-Agent"), caminho)

        tratadores = {
            "/painel/utilizadores": self._post_utilizadores,
            "/painel/automatizacao": self._post_automatizacao,
            "/painel/newsletter": self._post_newsletter,
            "/painel/perfil": self._post_perfil,
            "/painel/api/previa": self._post_previa,
        }
        tratador = tratadores.get(caminho)
        if tratador is None:
            self.send_error(404)
            return

        lido = self._ler_formulario()
        if lido is None:
            return
        campos, ficheiros = lido
        if not auth.csrf_valido(participante, campos.get("csrf")):
            # Isto nao acontece por acidente: o cookie vai com SameSite=Lax e
            # nao viaja num POST de outro sitio. Um simbolo errado e alguem a
            # tentar, ou um formulario aberto de antes de o segredo mudar - e
            # nos dois casos vale a pena ficar escrito.
            registo_servidor.anotar(
                registo_servidor.AVISO,
                f"símbolo de formulário inválido em {caminho}"
                f" ({participante})",
                "http",
            )
            self.send_error(403, "pedido não reconhecido")
            return
        tratador(campos, ficheiros, participante)

    def _entrar(self) -> None:
        endereco = self._endereco()
        if not _limite_entrada.permitir(endereco):
            self._responder(
                _pagina_entrada(
                    "Demasiadas tentativas. Tenta daqui a 15 minutos."
                ),
                "text/html; charset=utf-8",
            )
            return
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(min(tamanho, 4096)).decode("utf-8", errors="replace")
        codigo = parse_qs(corpo).get("codigo", [""])[0]
        participante = auth.participante_do_codigo(codigo)
        if participante is None:
            registo_servidor.anotar(
                registo_servidor.AVISO, f"código recusado de {endereco}", "entrada"
            )
            self._responder(
                _pagina_entrada("Código inválido."), "text/html; charset=utf-8"
            )
            return
        _limite_entrada.limpar(endereco)
        sessao = auth.criar_sessao(participante, auth.segredo())
        with uso.partilhada() as registo:
            uso.registar(registo, participante, uso.EVENTO_ENTRADA)
        registo_servidor.anotar(
            registo_servidor.INFO, f"{participante} entrou", "entrada"
        )
        seguro = "; Secure" if protecao.veio_por_tunel(self) else ""
        self._para(
            "/",
            cookie=(
                f"{auth.NOME_COOKIE}={sessao}; Path=/; HttpOnly; SameSite=Lax"
                f"{seguro}; Max-Age={auth.VALIDADE_DIAS * 86400}"
            ),
        )

    def _ler_formulario(self):
        """`(campos, ficheiros)`, ou None se o pedido ja foi respondido.

        Recusa antes de ler quando o `Content-Length` anunciado passa do limite:
        ler para memoria um corpo que ja se sabe ser grande demais e fazer o
        trabalho de quem o mandou. A ligacao fecha-se porque o corpo fica no
        socket sem ser lido, e o pedido seguinte encontraria lixo.
        """
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho <= 0:
            return {}, []
        if tamanho > media.LIMITE_CORPO:
            self.close_connection = True
            self.send_error(413, "corpo demasiado grande")
            return None
        corpo = self.rfile.read(tamanho)
        tipo = self.headers.get("Content-Type") or ""
        if tipo.lower().startswith("multipart/form-data"):
            return media.analisar_multipart(corpo, tipo)
        texto = corpo.decode("utf-8", errors="replace")
        campos = {
            chave: valores[0]
            for chave, valores in parse_qs(texto, keep_blank_values=True).items()
        }
        return campos, []

    # ---------------------------------------------------- accoes do painel

    def _post_utilizadores(self, campos, ficheiros, participante) -> None:
        accao = campos.get("accao", "")
        rotulo = (campos.get("rotulo") or "").strip()
        destino = "/painel/utilizadores"

        if accao == "revogar":
            if rotulo == participante:
                painel.deixar_recado(
                    participante,
                    "Não te podes revogar a ti mesmo — ficavas de fora do painel.",
                    mau=True,
                )
            elif auth.revogar(rotulo):
                registo_servidor.anotar(
                    registo_servidor.AVISO,
                    f"{participante} revogou {rotulo}",
                    "gestao",
                )
                painel.deixar_recado(
                    participante,
                    f"{rotulo} revogado. O código deixou de funcionar e a sessão"
                    " aberta fechou-se.",
                )
            else:
                painel.deixar_recado(
                    participante, f"Não encontrei {rotulo}.", mau=True
                )
            self._para(destino)
            return

        if accao == "novo-codigo":
            codigo = auth.novo_codigo(rotulo)
            if codigo is None:
                painel.deixar_recado(
                    participante, f"Não encontrei {rotulo}.", mau=True
                )
            else:
                registo_servidor.anotar(
                    registo_servidor.AVISO,
                    f"{participante} gerou código novo para {rotulo}",
                    "gestao",
                )
                painel.deixar_recado(
                    participante,
                    f"Código novo para {rotulo}. A sessão anterior foi fechada.",
                    codigos=[(codigo, rotulo)],
                )
            self._para(destino)
            return

        if accao == "criar":
            bruto = (campos.get("quantos") or "1").strip()
            quantos = int(bruto) if bruto.isdigit() else 0
            if not 1 <= quantos <= 40:
                painel.deixar_recado(
                    participante, "Quantos? Entre 1 e 40.", mau=True
                )
                self._para(destino)
                return
            prefixo = "admin" if campos.get("papel") == "admin" else "aluno"
            novos = auth.criar_participantes(quantos, prefixo)
            registo_servidor.anotar(
                registo_servidor.AVISO,
                f"{participante} criou {quantos} código(s) de {prefixo}",
                "gestao",
            )
            painel.deixar_recado(
                participante,
                f"{quantos} código(s) criado(s). Copia-os agora.",
                codigos=sorted(novos.items(), key=lambda par: par[1]),
            )
            self._para(destino)
            return

        self.send_error(400, "ação desconhecida")

    def _post_automatizacao(self, campos, ficheiros, participante) -> None:
        accao = campos.get("accao", "")
        comecou, porque = operacoes.iniciar(accao)
        if comecou:
            registo_servidor.anotar(
                registo_servidor.INFO,
                f"{participante} pediu: {operacoes.NOMES[accao]}",
                "gestao",
            )
            painel.deixar_recado(
                participante,
                f"{operacoes.NOMES[accao]}: a correr. O que vai dizendo aparece"
                " na consola abaixo.",
            )
        else:
            painel.deixar_recado(participante, porque.capitalize(), mau=True)
        self._para("/painel/automatizacao")

    def _post_newsletter(self, campos, ficheiros, participante) -> None:
        accao = campos.get("accao", "")
        bruto = (campos.get("id") or "").strip()
        identificador = int(bruto) if bruto.isdigit() else None

        if accao == "apagar-media":
            nome = campos.get("nome") or ""
            if media.apagar(nome):
                painel.deixar_recado(participante, "Ficheiro apagado.")
            else:
                painel.deixar_recado(
                    participante, "Não consegui apagar esse ficheiro.", mau=True
                )
            self._para("/painel/newsletter")
            return

        if accao == "apagar":
            if identificador is not None and newsletter.apagar(identificador):
                painel.deixar_recado(participante, "Post apagado.")
            else:
                painel.deixar_recado(participante, "Esse post já não existe.", mau=True)
            self._para("/painel/newsletter")
            return

        if accao in ("publicar", "despublicar"):
            quer = accao == "publicar"
            # Vindo do editor, guarda-se o texto que esta no ecra antes de
            # publicar: publicar uma versao mais antiga do que a que se esta a
            # ver seria a pior surpresa possivel neste botao.
            if identificador is not None and "corpo" in campos:
                newsletter.guardar(
                    campos.get("titulo", ""),
                    campos.get("corpo", ""),
                    participante,
                    identificador=identificador,
                    publicado=quer,
                )
                post = newsletter.obter(identificador)
            else:
                post = (
                    newsletter.marcar_publicado(identificador, quer)
                    if identificador is not None
                    else None
                )
            if post is None:
                painel.deixar_recado(participante, "Esse post já não existe.", mau=True)
                self._para("/painel/newsletter")
                return
            painel.deixar_recado(
                participante,
                "Publicado. A turma já o vê em /novidades."
                if quer
                else "Voltou a rascunho. Deixou de aparecer em /novidades.",
            )
            self._para(f"/painel/newsletter?id={post.id}")
            return

        if accao in ("guardar", "carregar"):
            post = newsletter.guardar(
                campos.get("titulo", ""),
                campos.get("corpo", ""),
                participante,
                identificador=identificador,
            )
            if accao == "guardar":
                painel.deixar_recado(participante, "Guardado.")
                self._para(f"/painel/newsletter?id={post.id}")
                return

            escolhidos = [f for f in ficheiros if f.campo == "media"]
            if not escolhidos:
                painel.deixar_recado(
                    participante, "Guardado, mas não escolheste ficheiro.", mau=True
                )
                self._para(f"/painel/newsletter?id={post.id}")
                return
            nome, erro = media.guardar(escolhidos[0])
            if erro:
                painel.deixar_recado(participante, f"O ficheiro não entrou: {erro}", mau=True)
                self._para(f"/painel/newsletter?id={post.id}")
                return
            juntado = (post.corpo.rstrip() + "\n\n" + media.marcacao_de(nome) + "\n")
            post = newsletter.guardar(
                post.titulo, juntado, participante, identificador=post.id
            )
            painel.deixar_recado(
                participante, "Ficheiro carregado e inserido no fim do texto."
            )
            self._para(f"/painel/newsletter?id={post.id}")
            return

        self.send_error(400, "ação desconhecida")

    def _post_perfil(self, campos, ficheiros, participante) -> None:
        accao = campos.get("accao", "")
        if accao == "apagar":
            atual = media.perfil_de(participante)
            if atual:
                try:
                    (media.PASTA_PERFIL / atual).unlink()
                    painel.deixar_recado(participante, "Foto removida.")
                except OSError as erro:
                    painel.deixar_recado(
                        participante, f"Não consegui remover: {erro}", mau=True
                    )
            self._para("/painel/perfil")
            return

        escolhidos = [f for f in ficheiros if f.campo == "foto"]
        if not escolhidos:
            painel.deixar_recado(participante, "Não escolheste imagem.", mau=True)
            self._para("/painel/perfil")
            return
        _, erro = media.guardar_perfil(participante, escolhidos[0])
        if erro:
            painel.deixar_recado(participante, f"A foto não entrou: {erro}", mau=True)
        else:
            painel.deixar_recado(participante, "Foto guardada.")
        self._para("/painel/perfil")

    def _post_previa(self, campos, ficheiros, participante) -> None:
        self._responder(
            painel.json_previa(campos.get("corpo", "")),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        # A rede de seguranca existe porque isto corre sem ninguem a ver. Um
        # estouro dentro de um pedido matava o fio em silencio e o aluno via
        # apenas uma pagina que nao carrega; agora fica escrito no registo, que
        # e o que o painel mostra.
        try:
            self._tratar_get()
        except (TimeoutError, ConnectionError, BrokenPipeError):
            self.close_connection = True
        except Exception:
            registo_servidor.excecao(f"GET {self.path[:140]}", "http")
            try:
                self.send_error(500, "erro interno")
            except Exception:
                self.close_connection = True

    def _tratar_get(self):
        if self._excedeu_limite():
            return
        url = urlparse(self.path)
        parametros = parse_qs(url.query)

        if url.path == "/privacidade":
            corpo = _pagina(
                consulta="",
                opcoes="",
                novidades="",
                corpo=_pagina_privacidade(),
                pagina="privacidade",
                administrador=auth.e_administrador(self._participante()),
            )
            self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")
            return

        if url.path == "/favicon.ico":
            # A pagina declara `<link rel="icon">`, e mesmo assim os browsers
            # pedem /favicon.ico. Sem isto o pedido caia na barreira de sessao e
            # levava 403, o que enchia o registo de avisos sobre um pedido
            # perfeitamente normal. Fica antes da barreira, como a restante
            # marca: e o mesmo ficheiro que /estatico/icone.png.
            self._servir_estatico("/estatico/icone.png")
            return

        if url.path == "/robots.txt":
            # Nada aqui e para indexar: o motor e fechado por codigo e as
            # paginas de apoio nao interessam a robo nenhum. Fica declarado
            # ainda assim, porque um 403 nao diz a intencao.
            self._responder(
                b"User-agent: *\nDisallow: /\n", "text/plain; charset=utf-8"
            )
            return

        if url.path.startswith("/estatico/"):
            # Antes da barreira de sessao, e de proposito. Sao imagens da
            # marca, tipos de letra, a biblioteca de animacoes e os documentos
            # publicos - nada disto e sensivel, e a propria pagina de entrada
            # precisa deles. Enquanto estiveram atras da sessao, quem chegava
            # de fora via a pagina de entrada sem logotipo e sem tipos de letra.
            self._servir_estatico(url.path)
            return

        if url.path == "/sair":
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", f"{auth.NOME_COOKIE}=; Path=/; Max-Age=0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        participante = self._participante()
        if participante is None:
            if url.path in ("/", "/entrar"):
                self._responder(_pagina_entrada(), "text/html; charset=utf-8")
            else:
                self.send_error(403, "acesso restrito")
            return

        # Marcar presenca antes de servir o que for: e isto que faz a coluna
        # "visto" do painel dizer a verdade sobre quem esta ca. A escrita e
        # estrangulada em `presenca.py`, portanto isto nao custa um acesso a
        # disco por pedido.
        presenca.marcar(participante, self.headers.get("User-Agent"), url.path)
        administrador = auth.e_administrador(participante)

        if url.path.startswith("/media/") or url.path.startswith("/perfil/"):
            self._servir_media(url.path)
            return

        if url.path == "/painel" or url.path.startswith("/painel/"):
            if not administrador:
                self.send_error(403, "acesso restrito")
                return
            self._servir_painel(url, parametros, participante)
            return

        if url.path == "/sugerir":
            self._servir_sugestoes(parametros, participante)
            return
        if url.path == "/abrir":
            self._redirecionar(parametros, participante)
            return
        if url.path == "/documento":
            self._servir_documento(parametros, participante)
            return
        if url.path == "/preview":
            self._servir_preview(parametros, participante)
            return
        if url.path == "/novidades":
            corpo = _pagina(
                consulta="",
                opcoes=_opcoes(_disciplinas_disponiveis(), ""),
                novidades="",
                corpo=_pagina_novidades(administrador),
                pagina="novidades",
                administrador=administrador,
            )
            self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")
            return
        if url.path == "/estatisticas":
            # Passou a ser so do administrador, e passou a viver dentro do
            # painel. O endereco antigo continua a responder porque anda em
            # marcadores e em capturas de ecra do manual - reencaminha.
            if not administrador:
                self.send_error(403, "acesso restrito")
                return
            self._para(painel.caminho_de(painel.VISAO))
            return
        if url.path != "/":
            self.send_error(404)
            return

        consulta = parametros.get("q", [""])[0].strip()
        disciplina = parametros.get("d", [""])[0].strip()
        corrigida = parametros.get("corrigida", [""])[0] == "1"
        seccao = parametros.get("s", [""])[0].strip()
        if seccao not in mod_seccoes.SECCOES:
            seccao = ""
        exato = parametros.get("exato", [""])[0] == "1"
        pagina = paginacao.ler(parametros.get("pg", [""])[0])
        corpo = _montar_pagina(
            consulta, disciplina, participante, corrigida, seccao, exato, pagina
        )
        self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")

    def _para(self, destino: str, cookie: str | None = None) -> None:
        """303 para `destino`. Depois de um POST, sempre.

        Sem o reencaminhamento, recarregar a pagina repetia o pedido - e uma das
        accoes deste painel e revogar um acesso. O 303 e nao o 302 porque diz ao
        browser para trocar o metodo por GET, que e o que se quer aqui.

        `destino` nunca vem de fora: sao literais e ids numericos. Aceitar um
        endereco de fora seria transformar isto num reencaminhador aberto.
        """
        self.send_response(303)
        self.send_header("Location", destino)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        for chave, valor in protecao.CABECALHOS_SEGURANCA.items():
            self.send_header(chave, valor)
        self.end_headers()

    def _servir_media(self, caminho: str) -> None:
        """Imagens, GIFs, videos e retratos - atras da barreira de sessao.

        Fica dentro da sessao de proposito, ao contrario de `/estatico/`: aquilo
        e a marca e os tipos de letra, isto e conteudo que o administrador poe
        para a turma. Um endereco publico deixava a biblioteca de media do
        projeto acessivel a quem adivinhasse um nome.
        """
        se_perfil = caminho.startswith("/perfil/")
        if se_perfil:
            nome, pasta = caminho.removeprefix("/perfil/"), media.PASTA_PERFIL
        else:
            nome, pasta = caminho.removeprefix("/media/"), media.PASTA
        dados, tipo = media.ler(nome, pasta)
        if not dados:
            self.send_error(404)
            return
        # A media tem nome de resumo do conteudo: muda de nome quando muda, e
        # por isso pode ficar em cache um dia. O retrato tem nome de rotulo e e
        # substituido no mesmo nome - esse nao pode.
        self._responder(dados, tipo, cache=not se_perfil)

    def _servir_painel(self, url, parametros, participante: str) -> None:
        if url.path.startswith("/painel/api/"):
            self._api_painel(
                url.path.removeprefix("/painel/api/"), parametros, participante
            )
            return

        seccao = url.path.removeprefix("/painel").strip("/") or painel.VISAO
        if seccao not in painel.CHAVES:
            self.send_error(404)
            return

        contexto = painel.tirar_recado(participante)
        if seccao == painel.NEWSLETTER:
            bruto = parametros.get("id", [""])[0]
            if parametros.get("novo", [""])[0] == "1":
                contexto["novo"] = True
            elif bruto.isdigit():
                post = newsletter.obter(int(bruto))
                if post is None:
                    contexto["recado"] = "Esse post já não existe."
                    contexto["recado_mau"] = True
                else:
                    contexto["post"] = post

        with uso.partilhada() as registo:
            corpo = painel.pagina(seccao, participante, registo, contexto)
        self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")

    def _api_painel(self, nome: str, parametros, participante: str) -> None:
        if nome != "vivo":
            self.send_error(404)
            return
        bruto = parametros.get("desde", ["0"])[0]
        desde = int(bruto) if bruto.isdigit() else 0
        quero = parametros.get("quero", [""])[0][:60]
        origem = parametros.get("origem", [""])[0][:80]
        with uso.partilhada() as registo:
            corpo = painel.json_vivo(registo, quero, desde, origem)
        # Sem cache, e dito: e uma resposta que muda a cada dois segundos e meio
        # e que nao deve ficar guardada em intermediario nenhum.
        self._responder(corpo, "application/json; charset=utf-8", cache=False)

    def _servir_estatico(self, caminho: str) -> None:
        """Serve os ficheiros da marca e a biblioteca de animacoes."""
        nome = caminho.removeprefix("/estatico/")
        alvo = _ESTATICOS.get(nome)
        if alvo is None:
            self.send_error(404)
            return
        pasta, tipo = alvo
        try:
            dados = (pasta / nome).read_bytes()
        except OSError:
            self.send_error(404)
            return
        self._responder(dados, tipo, cache=True)

    def _doc_pedido(self, parametros):
        bruto = parametros.get("id", [""])[0]
        if not bruto.isdigit() or not CAMINHO_BANCO.exists():
            return None
        with storage.emprestada(CAMINHO_BANCO) as conexao:
            documentos = storage.carregar_documentos(conexao, [int(bruto)])
        return documentos.get(int(bruto))

    def _servir_sugestoes(self, parametros, participante: str) -> None:
        prefixo = parametros.get("q", [""])[0]
        encontradas = []
        if CAMINHO_BANCO.exists():
            with storage.emprestada(CAMINHO_BANCO) as indice:
                with uso.partilhada() as registo:
                    encontradas = sugestoes.sugerir(
                        registo, indice, participante, prefixo
                    )
        corpo = json.dumps(
            [{"texto": s.texto, "origem": s.origem} for s in encontradas],
            ensure_ascii=False,
        ).encode("utf-8")
        self._responder(corpo, "application/json; charset=utf-8")

    def _redirecionar(self, parametros, participante: str) -> None:
        doc = self._doc_pedido(parametros)
        if doc is None or not doc.origem.startswith(("http://", "https://")):
            self.send_error(404, "documento desconhecido")
            return
        posicao = parametros.get("p", [""])[0]
        with uso.partilhada() as registo:
            uso.registar(
                registo, participante, uso.EVENTO_ABERTURA,
                consulta=parametros.get("q", [""])[0],
                doc_id=doc.id,
                posicao=int(posicao) if posicao.isdigit() else None,
            )
        self.send_response(303)
        self.send_header("Location", doc.origem.replace("#pagina=", "#page="))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _servir_preview(self, parametros, participante: str) -> None:
        doc = self._doc_pedido(parametros)
        if doc is None:
            self.send_error(404, "documento desconhecido")
            return
        consulta = parametros.get("q", [""])[0]
        with uso.partilhada() as registo:
            uso.registar(
                registo, participante, uso.EVENTO_PREVIEW,
                consulta=consulta, doc_id=doc.id,
            )
        self._responder(fragmento(doc, consulta).encode("utf-8"), "text/html; charset=utf-8")

    def _servir_documento(self, parametros, participante: str) -> None:
        doc = self._doc_pedido(parametros)
        if doc is None:
            self.send_error(404, "documento desconhecido")
            return
        posicao = parametros.get("p", [""])[0]
        with uso.partilhada() as registo:
            uso.registar(
                registo, participante, uso.EVENTO_ABERTURA,
                consulta=parametros.get("q", [""])[0],
                doc_id=doc.id,
                posicao=int(posicao) if posicao.isdigit() else None,
            )
        try:
            dados, nome = _ler_arquivo(doc.origem)
        except (FileNotFoundError, KeyError, PermissionError, zipfile.BadZipFile):
            self.send_error(410, "ficheiro de origem indisponível")
            return
        tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        self._responder(dados, tipo, nome)

    def _responder(
        self, corpo: bytes, tipo: str, nome: str | None = None,
        cache: bool = False,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        if cache:
            # As imagens da marca vao em todas as paginas e nunca mudam entre
            # arranques. Sem isto eram quatro pedidos por busca.
            self.send_header("Cache-Control", "public, max-age=86400")
        for chave, valor in protecao.CABECALHOS_SEGURANCA.items():
            self.send_header(chave, valor)
        if protecao.veio_por_tunel(self):
            self.send_header(*protecao.CABECALHO_HSTS)
        if nome:
            seguro = protecao.sanear_nome_ficheiro(nome)
            self.send_header(
                "Content-Disposition", f'inline; filename="{seguro}"'
            )
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args) -> None:
        """Deixou de ser um `pass`: o painel mostra isto ao vivo.

        Em memoria e nao em disco, porque a linha de um pedido leva consigo o
        que a pessoa escreveu na caixa de busca (`GET /?q=...`) - e isso nao tem
        razao para ficar gravado sem prazo de validade. Avisos e erros vao a
        disco; esses nao levam consultas.
        """
        try:
            texto = formato % args
            # A consola do painel pergunta por novidades de dois em dois
            # segundos e meio. Registar essa pergunta fazia o registo encher-se
            # de si proprio: vinte e quatro linhas por minuto a dizer que o
            # painel esteve a ver o painel, e o acontecimento verdadeiro
            # enterrado no meio. Visto ao vivo com a pagina aberta.
            if "/painel/api/" in texto:
                return
            registo_servidor.anotar(registo_servidor.INFO, texto, "http")
        except Exception:
            pass

    def log_error(self, formato, *args) -> None:
        try:
            registo_servidor.anotar(registo_servidor.AVISO, formato % args, "http")
        except Exception:
            pass


def iniciar(porta: int = 8080, host: str = "127.0.0.1") -> None:
    # Apagar o que passou do prazo e a primeira coisa que se faz, antes de
    # aceitar um pedido. Nao ha agendador: o servidor e reiniciado com
    # frequencia e isso chega. O que nao chegava era nao haver prazo nenhum.
    try:
        with uso.partilhada() as registo:
            saidos = uso.apagar_antigos(registo)
        if saidos:
            print(f"Registo: {saidos} eventos com mais de "
                  f"{uso.DIAS_DE_RETENCAO} dias apagados.")
    except Exception as erro:
        print(f"AVISO: nao foi possivel limpar o registo de uso ({erro}).")

    if not auth.carregar_participantes():
        print("AVISO: nenhum participante criado ainda.")
        print("       python main.py participantes --criar 8")
        print()
    try:
        servidor = _Servidor((host, porta), _Manipulador)
    except OSError:
        print(f"ERRO: a porta {porta} ja esta a ser usada por outro processo.")
        print("      Feche o servidor anterior ou use --porta <outra>.")
        return
    if host != "127.0.0.1":
        print(f"ATENCAO: a aceitar ligacoes de {host} - acesso so por codigo.")
    registo_servidor.anotar(
        registo_servidor.INFO, f"servidor no ar em {host}:{porta}", "arranque"
    )
    print(f"Madalena no ar em http://{host}:{porta} (Ctrl+C encerra)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        servidor.server_close()
