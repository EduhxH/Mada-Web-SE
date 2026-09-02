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
from app.models import novidades
from app.interface import auth, disciplina as pagina_disciplina, estatisticas, protecao
from app.interface import estilo, icones, movimento, paginacao
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
# Nome do ficheiro -> (pasta, tipo). Lista fechada: o nome vem do endereco,
# portanto vem de fora, e comparar contra uma lista e mais simples de ler - e
# de confiar - do que tentar limpar ".." de um caminho.
_ESTATICOS = {
    "gato.png": (RAIZ_MARCA, "image/png"),
    "lettering.png": (RAIZ_MARCA, "image/png"),
    "icone.png": (RAIZ_MARCA, "image/png"),
    "404.png": (RAIZ_MARCA, "image/png"),
    "anime.min.js": (RAIZ_JS, "application/javascript; charset=utf-8"),
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


def _caixa_busca(consulta: str, opcoes: str, autofoco: bool = False) -> str:
    """A caixa de pesquisa. A mesma no topo dos resultados e ao centro da entrada."""
    foco = " autofocus" if autofoco else ""
    return (
        '<form class="busca" action="/" method="get">'
        '<span class="campo">'
        f'<span class="ic-lupa">{icones.svg("lupa", 17)}</span>'
        f'<input type="text" name="q" value="{consulta}"{foco} autocomplete="off" '
        'placeholder="procurar no material da escola">'
        '<div id="sugestoes"></div></span>'
        f'<span class="filtro"><select name="d" aria-label="disciplina">'
        f"{opcoes}</select></span>"
        '<button class="icone-botao solido lupa" type="submit" '
        f'aria-label="pesquisar">{icones.svg("seta-dir", 18)}</button>'
        "</form>"
    )


def _pagina(consulta: str, opcoes: str, novidades: str, corpo: str,
            abas: str = "") -> str:
    """O esqueleto das paginas com resultados."""
    return (
        f"{estilo.cabeca('Madalena')}\n"
        "<body>\n"
        '<header class="topo">'
        '<div class="topo-linha">'
        f"{estilo.marca()}"
        f"{_caixa_busca(consulta, opcoes)}"
        f"{estilo.acoes()}"
        "</div>"
        f"{abas}"
        "</header>\n"
        '<main><div class="coluna">'
        f"{novidades}{corpo}"
        "</div></main>\n"
        '<div id="painel"></div>\n'
        '<footer>índice local &middot; sem serviços externos &middot; '
        '<a href="/novidades">material novo</a></footer>\n'
        f"<script>{_GUIAO}{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}\n"
        "</body>\n</html>"
    )


def _pagina_entrada(erro: str = "") -> bytes:
    """A porta de entrada dos alunos que estao a testar.

    Um cartao ao centro: a marca, o aviso de que isto e um teste fechado, a
    caixa do codigo e o que fica registado. Nada mais - quem chega aqui ou tem
    codigo ou nao tem, e nao ha nada para explorar antes disso.
    """
    bloco = f'<p class="erro">{html.escape(erro)}</p>' if erro else ""
    corpo = (
        f"{estilo.cabeca('Madalena - entrar')}\n"
        "<body>\n"
        '<div class="centro cheio">'
        f"{estilo.marca(grande=True)}"
        '<div class="cartao-entrada">'
        f'<span class="etiqueta-beta">{icones.svg("brilho", 13)}Teste fechado</span>'
        '<p class="diz">Buscador do material da escola.<br>'
        "Entra com o c\u00f3digo que te deram.</p>"
        '<form method="post" action="/entrar">'
        '<input class="codigo" type="text" name="codigo" '
        'placeholder="C\u00d3DIGO-ACESSO" autofocus autocomplete="off" '
        'aria-label="c\u00f3digo de acesso">'
        '<button class="botao-entrar" type="submit">entrar'
        f'{icones.svg("seta-dir", 16)}</button>'
        "</form>"
        f"{bloco}"
        "</div>"
        '<div class="aviso">'
        "Projeto em fase de teste, restrito a participantes convidados. "
        "Para avaliar a ferramenta s\u00e3o registadas: as pesquisas feitas, se houve "
        "resultados e que documentos foram abertos. <b>N\u00e3o</b> s\u00e3o guardados nomes, "
        "endere\u00e7os IP nem qualquer dado pessoal &mdash; cada participante \u00e9 "
        "identificado por um r\u00f3tulo (aluno-01, aluno-02...). "
        "N\u00e3o partilhes o teu c\u00f3digo."
        "</div>"
        '<div class="abaixo">'
        f"{estilo.botao_tema()}"
        "</div>"
        "</div>\n"
        f"<script>{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}\n"
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
) -> tuple[str, str]:
    """Devolve (corpo, abas). As abas vivem no cabecalho, o corpo no meio."""
    sugestao = _bloco_correcao(resultado, consulta, disciplina) + _bloco_sugestao(
        resultado, consulta, disciplina
    )
    if not resultado.documentos:
        vazio = (
            '<div class="vazio-marca">'
            '<img src="/estatico/gato.png" alt=""></div>'
            f'<p class="vazio">Nenhum resultado para '
            f'<b>{html.escape(consulta)}</b>.</p>'
        )
        return sugestao + vazio, ""

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
    abas = _abas(resultado.documentos, grupos, consulta, disciplina, seccao)

    escolhidos = (
        mod_seccoes.filtrar(resultado.documentos, seccao)
        if seccao
        else resultado.documentos
    )
    janela = paginacao.calcular(len(escolhidos), pagina)

    corpo = [
        f'<p class="meta">{_contagem(len(escolhidos))}{_tempo(segundos)}{aviso}</p>',
        sugestao,
        _corpo_resultados(
            escolhidos, consulta, disciplina, termos, seccao, paginas,
            mostrar_pontuacao, janela,
        ),
        _barra_paginas(janela, consulta, disciplina, seccao),
    ]
    return "\n".join(bloco for bloco in corpo if bloco), abas


def _abas(documentos, grupos, consulta: str, disciplina: str, seccao: str) -> str:
    """As seccoes viraram separadores, no lugar onde o Google poe os dele.

    Antes, cada seccao mostrava cinco resultados e um "ver os N" ao lado. Isso
    nao se paginava: a pagina 2 de um ecra com quatro listas de cinco nao quer
    dizer nada. Como separadores, cada vista e uma lista corrida - e uma lista
    corrida pagina-se.
    """
    if len(grupos) <= 1:
        return ""
    itens = [("", "Todos", len(documentos))]
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

    da_rede = doc.origem.startswith(("http://", "https://"))
    origem = [
        icones.svg("globo" if da_rede else "ficheiro", 14),
        f'<span class="fonte">{html.escape(_fonte_legivel(doc.origem))}</span>',
    ]
    if doc.disciplina and mostrar_disciplina:
        origem.append(
            f'<span class="disciplina">{html.escape(doc.disciplina)}</span>'
        )
    quando = _data_legivel(getattr(doc, "data", ""))
    if quando:
        origem.append('<span class="sep">&middot;</span>')
        origem.append(f'<span class="quando">{quando}</span>')

    # A pontuacao e um numero de depuracao. Nao diz nada a um aluno e, no
    # telemovel, empurrava metade do titulo para a linha seguinte. Fica para
    # quem afina o ranqueamento.
    pontos = (
        f'<span class="pontuacao">{pontuacao:.4f}</span>'
        if mostrar_pontuacao
        else ""
    )
    return (
        f'<div class="resultado" data-id="{doc.id}">'
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
        "</div>"
    )


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


def _pagina_inicial(opcoes: str) -> str:
    """A entrada. Tudo o que ca esta serve para apontar para a caixa de busca."""
    return (
        f"{estilo.cabeca('Madalena')}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{estilo.acoes()}"
        "</div></header>\n"
        '<div class="centro">'
        f"{estilo.marca(grande=True)}"
        '<h1 class="lema">Tudo da escola. Num s\u00edtio s\u00f3.</h1>'
        '<p class="sublema">Horarios, fichas, regulamentos e paginas do site, '
        "num indice unico.</p>"
        f"{_caixa_busca('', opcoes, autofoco=True)}"
        '<div class="abaixo">'
        f'<a class="pastilha" href="/novidades">{icones.svg("brilho", 15)}'
        "material novo</a>"
        f'<a class="pastilha" href="/estatisticas">{icones.svg("grafico", 15)}'
        "estatisticas</a>"
        "</div>"
        "</div>\n"
        f"<script>{_GUIAO}{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"{movimento.marcacao()}\n"
        "</body>\n</html>"
    )


def _montar_pagina(
    consulta: str, disciplina: str, participante: str,
    corrigida: bool = False, seccao: str = "", exato: bool = False,
    pagina: int = 1,
) -> str:
    disciplinas: list[str] = []
    abas = ""
    if not CAMINHO_BANCO.exists():
        corpo = (
            '<p class="vazio">Índice não encontrado. '
            "Rode: python main.py indexar &lt;caminho&gt;</p>"
        )
    else:
        # A ligacao ao indice e uma so para o processo todo, e a tranca deixa
        # passar uma busca de cada vez. Parece o contrario do que se quer, mas
        # foi medido: com oito alunos em simultaneo, ligacao nova por pedido
        # dava 6.9 s e esta da 0.2 s. Ver storage.emprestada.
        resultado = None
        segundos = 0.0
        with storage.emprestada(CAMINHO_BANCO) as conexao:
            disciplinas = storage.listar_disciplinas(conexao)
            if not consulta and not disciplina:
                return _pagina_inicial(_opcoes(disciplinas, ""))
            if not consulta and disciplina:
                with uso.partilhada() as registo:
                    corpo = pagina_disciplina.pagina(conexao, registo, disciplina)
                return _pagina(
                    consulta="",
                    opcoes=_opcoes(disciplinas, disciplina),
                    novidades=_aviso_novidades(),
                    corpo=corpo,
                )
            if consulta:
                comeco = time.perf_counter()
                resultado = hibrida.buscar(
                    conexao, consulta, disciplina=disciplina or None,
                    permitir_ou=not exato,
                )
                segundos = time.perf_counter() - comeco
                # So a primeira pagina conta como busca. Sem isto, folhear ate
                # a pagina 5 registava cinco buscas iguais: a mesma pergunta
                # passava a parecer cinco vezes mais popular do que e, e o
                # numero de buscas sem resultado ficava dividido por quantas
                # paginas o aluno virou.
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

        # Fora da tranca: montar o HTML sao dezena de milissegundos de Python
        # que nao tocam na base de dados, e segurar a fila com eles seria
        # fazer os outros alunos esperar por nada.
        corpo, abas = (
            _renderizar(
                consulta, disciplina, resultado, seccao,
                auth.e_administrador(participante), pagina, segundos,
            )
            if resultado is not None
            else ("", "")
        )
    return _pagina(
        consulta=html.escape(consulta, quote=True),
        opcoes=_opcoes(disciplinas, disciplina),
        novidades=_aviso_novidades(),
        corpo=corpo,
        abas=abas,
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


def _pagina_novidades() -> str:
    recentes = novidades.recentes()
    if not recentes:
        corpo = '<p class="vazio">Nada de novo nos últimos dias.</p>'
    else:
        linhas = []
        for item in recentes:
            titulo = html.escape(item.titulo)
            disciplina = html.escape(item.disciplina)
            # Leva a busca ca dentro, nao ao Moodle: o url guardado e
            # relativo ao Moodle e resolveria contra o servidor errado.
            procura = urlencode({"q": item.titulo})
            linhas.append(
                f'<li><span class="disciplina">{disciplina}</span>'
                f'<a href="/?{procura}">{titulo}</a>'
                f'<span class="quando">{html.escape(item.data)}</span></li>'
            )
        corpo = f'<ul class="novo-lista">{"".join(linhas)}</ul>'
    return (
        f'<h2 class="sec">material novo</h2>{corpo}'
        '<p class="voltar"><a href="/">voltar à busca</a></p>'
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
        return auth.validar_sessao(item.value, auth.segredo())

    def do_POST(self):
        if urlparse(self.path).path != "/entrar":
            self.send_error(404)
            return
        if self._excedeu_limite():
            return
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
            self._responder(_pagina_entrada("Código inválido."), "text/html; charset=utf-8")
            return
        _limite_entrada.limpar(endereco)
        sessao = auth.criar_sessao(participante, auth.segredo())
        with uso.partilhada() as registo:
            uso.registar(registo, participante, uso.EVENTO_ENTRADA)
        self.send_response(303)
        self.send_header("Location", "/")
        seguro = "; Secure" if protecao.veio_por_tunel(self) else ""
        self.send_header(
            "Set-Cookie",
            f"{auth.NOME_COOKIE}={sessao}; Path=/; HttpOnly; SameSite=Lax"
            f"{seguro}; Max-Age={auth.VALIDADE_DIAS * 86400}",
        )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self._excedeu_limite():
            return
        url = urlparse(self.path)
        parametros = parse_qs(url.query)

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

        if url.path.startswith("/estatico/"):
            self._servir_estatico(url.path)
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
                corpo=_pagina_novidades(),
            )
            self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")
            return
        if url.path == "/estatisticas":
            with uso.partilhada() as registo:
                corpo = estatisticas.pagina(
                    registo, auth.e_administrador(participante)
                ).encode("utf-8")
            self._responder(corpo, "text/html; charset=utf-8")
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
        if nome:
            seguro = protecao.sanear_nome_ficheiro(nome)
            self.send_header(
                "Content-Disposition", f'inline; filename="{seguro}"'
            )
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args) -> None:
        pass


def iniciar(porta: int = 8080, host: str = "127.0.0.1") -> None:
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
    print(f"Madalena no ar em http://{host}:{porta} (Ctrl+C encerra)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        servidor.server_close()
