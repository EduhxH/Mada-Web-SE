import html
import mimetypes
import zipfile
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import parse_qs, urlencode, urlparse

from app.analytics import uso
from app.indexing import storage
from app.models import novidades
from app.interface import auth, disciplina as pagina_disciplina, estatisticas, protecao
from app.interface.preview import fragmento, resolver_origem
from app.indexing.tokenizer import tokenizar
import json

from app.search import sugestoes
from app.search import seccoes as mod_seccoes
from app.search.query import MODO_OU, MODO_QUORUM, buscar_detalhado
from app.search.snippet import gerar_trecho

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
RAIZ_DADOS = (Path("data") / "raw").resolve()
LIMITE_RESULTADOS = 20
POR_SECCAO = 5

_MODELO = Template("""<!doctype html>
<html lang="pt-pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madalena</title>
<style>
body { font-family: Georgia, "Times New Roman", serif; max-width: 660px; margin: 48px auto; padding: 0 16px; color: #1a1a1a; background: #fdfdfd; }
h1 { font-size: 26px; font-weight: normal; letter-spacing: 2px; margin-bottom: 4px; }
h1 a { color: inherit; text-decoration: none; }
.sub { color: #777; font-size: 13px; margin: 0 0 20px; }
form { margin: 0 0 24px; position: relative; }
.campo { position: relative; display: inline-block; width: 60%; }
#sugestoes { display: none; position: absolute; left: 0; right: 0; top: 100%; background: #fff; border: 1px solid #999; border-top: none; z-index: 20; max-height: 300px; overflow-y: auto; }
#sugestoes div { padding: 7px 10px; cursor: pointer; font-size: 15px; display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
#sugestoes div:hover, #sugestoes div.ativa { background: #eef1f7; }
#sugestoes .fonte { font-size: 10px; color: #999; text-transform: lowercase; white-space: nowrap; }
input[type=text] { width: 100%; box-sizing: border-box; padding: 8px 10px; font-size: 16px; border: 1px solid #999; background: #fff; font-family: inherit; }
select { padding: 8px 6px; font-size: 14px; border: 1px solid #999; background: #fff; font-family: inherit; max-width: 34%; }
button { padding: 8px 16px; font-size: 15px; border: 1px solid #999; background: #eee; cursor: pointer; font-family: inherit; margin-top: 6px; }
.meta { color: #666; font-size: 13px; margin-bottom: 8px; }
.sugestao { font-size: 15px; margin: 0 0 20px; }
.sugestao a { color: #7a2020; }
.resultado { margin-bottom: 20px; }
.titulo { font-size: 16px; margin: 0; }
.titulo a { color: #24418c; text-decoration: none; }
.titulo a:hover { text-decoration: underline; }
.pontuacao { color: #999; font-size: 12px; margin-left: 6px; }
.disciplina { color: #555; font-size: 12px; border: 1px solid #ccc; padding: 1px 5px; margin-right: 6px; }
.trecho { margin: 3px 0 0; font-size: 14px; line-height: 1.5; color: #333; }
.vazio { color: #666; }
h2.sec { font-size: 12px; font-weight: normal; color: #666; margin: 26px 0 10px; border-bottom: 1px solid #e5e5e5; padding-bottom: 4px; text-transform: lowercase; letter-spacing: .6px; display: flex; justify-content: space-between; align-items: baseline; }
h2.sec .conta { color: #aaa; font-size: 11px; }
h2.sec a { color: #24418c; font-size: 11px; text-decoration: none; }
h2.sec a:hover { text-decoration: underline; }
.voltar { font-size: 13px; margin: 0 0 16px; }
.voltar a { color: #24418c; }
h2.dsc { font-size: 13px; font-weight: normal; color: #777; margin: 26px 0 8px; border-bottom: 1px solid #e5e5e5; padding-bottom: 4px; text-transform: lowercase; letter-spacing: .5px; }
.temas { display: flex; flex-wrap: wrap; gap: 6px; }
.tema { display: inline-block; border: 1px solid #ccc; padding: 3px 9px; font-size: 13px; color: #24418c; text-decoration: none; background: #fff; }
.tema:hover { background: #eef1f7; border-color: #99a; }
ul.dsc { list-style: none; padding: 0; margin: 0; font-size: 14px; line-height: 1.9; }
ul.dsc a { color: #24418c; text-decoration: none; }
ul.dsc a:hover { text-decoration: underline; }
.vezes { color: #aaa; font-size: 11px; }
.novo { font-size: 13px; color: #555; background: #f5f2e8; border: 1px solid #e0d8c0; padding: 6px 10px; margin: 0 0 16px; }
.novo a { color: #24418c; }
ul.novo-lista { list-style: none; padding: 0; margin: 0; }
ul.novo-lista li { padding: 6px 0; border-bottom: 1px solid #eee; font-size: 14px; }
ul.novo-lista .quando { color: #999; font-size: 12px; margin-left: 6px; }
footer { margin-top: 48px; border-top: 1px solid #ddd; padding-top: 10px; color: #aaa; font-size: 12px; }
footer a { color: #aaa; }

.prever { display: none; font-size: 12px; color: #24418c; background: none; border: 1px solid #ccc; padding: 2px 8px; margin-top: 6px; cursor: pointer; font-family: inherit; }
.pv-inline:not(:empty) { border-left: 2px solid #ddd; padding: 8px 0 2px 10px; margin-top: 8px; }
#painel { display: none; position: fixed; width: 300px; left: calc(50% + 350px); background: #fff; border: 1px solid #bbb; padding: 12px 14px; box-shadow: 0 2px 10px rgba(0,0,0,.10); max-height: 70vh; overflow-y: auto; }
.pv-etiquetas { margin: 0 0 4px; font-size: 11px; color: #777; text-transform: lowercase; }
.pv-ficheiro { margin: 0; font-size: 13px; color: #1a1a1a; word-break: break-word; }
.pv-zip { margin: 2px 0 0; font-size: 11px; color: #999; }
.pv-texto { margin: 10px 0 0; font-size: 13px; line-height: 1.55; color: #333; }

@media (max-width: 600px) {
  body { margin: 24px auto; }
  .campo, select { width: 100%; max-width: 100%; box-sizing: border-box; margin-bottom: 6px; }
}
@media (max-width: 1024px) {
  #painel { display: none !important; }
  .prever { display: inline-block; }
}
</style>
</head>
<body>
<h1><a href="/">Madalena</a></h1>
<p class="sub">motor de busca escolar</p>
$novidades
<form action="/" method="get">
<span class="campo"><input type="text" name="q" value="$consulta" autofocus autocomplete="off"><div id="sugestoes"></div></span>
<select name="d">$opcoes</select>
<button type="submit">buscar</button>
</form>
$corpo
<div id="painel"></div>
<footer>indice local &middot; sem APIs externas &middot; <a href="/estatisticas">estatisticas</a> &middot; <a href="/sair">sair</a></footer>
<script>
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
    var lista = [];
    var ativa = -1;
    var espera = null;
    var ultimoPedido = "";

    function fechar() {
      caixa.style.display = "none";
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
</script>
</body>
</html>
""")


_ENTRADA = """<!doctype html>
<html lang="pt-pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madalena</title>
<style>
body { font-family: Georgia, "Times New Roman", serif; max-width: 420px; margin: 90px auto; padding: 0 20px; color: #1a1a1a; background: #fdfdfd; }
h1 { font-size: 26px; font-weight: normal; letter-spacing: 2px; margin-bottom: 4px; }
.sub { color: #777; font-size: 13px; margin: 0 0 26px; }
input { width: 100%; padding: 10px; font-size: 17px; border: 1px solid #999; font-family: inherit; box-sizing: border-box; letter-spacing: 2px; text-transform: uppercase; }
button { margin-top: 10px; padding: 9px 18px; font-size: 15px; border: 1px solid #999; background: #eee; cursor: pointer; font-family: inherit; }
.erro { color: #7a2020; font-size: 13px; margin-top: 12px; }
.aviso { margin-top: 34px; border-top: 1px solid #ddd; padding-top: 12px; color: #777; font-size: 12px; line-height: 1.6; }
</style>
</head>
<body>
<h1>Madalena</h1>
<p class="sub">motor de busca escolar &middot; acesso restrito</p>
<form method="post" action="/entrar">
<input type="text" name="codigo" placeholder="CODIGO-ACESSO" autofocus autocomplete="off">
<button type="submit">entrar</button>
</form>
__ERRO__
<div class="aviso">
Projeto em fase de teste, restrito a participantes convidados.
Para avaliar a ferramenta sao registados: as pesquisas feitas, se houve
resultados e que documentos foram abertos. <b>Nao</b> sao guardados nomes,
enderecos IP nem qualquer dado pessoal &mdash; cada participante e
identificado por um rotulo (aluno-01, aluno-02...).
Nao partilhes o teu codigo.
</div>
</body>
</html>
"""


def _pagina_entrada(erro: str = "") -> bytes:
    bloco = f'<p class="erro">{html.escape(erro)}</p>' if erro else ""
    return _ENTRADA.replace("__ERRO__", bloco).encode("utf-8")


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
        '<p class="sugestao">Sera que quis dizer: '
        f'<a href="{html.escape(destino)}">{html.escape(corrigida)}</a>?</p>'
    )


def _renderizar(consulta: str, disciplina: str, resultado, seccao: str = "") -> str:
    sugestao = _bloco_correcao(resultado, consulta, disciplina) + _bloco_sugestao(
        resultado, consulta, disciplina
    )
    if not resultado.documentos:
        vazio = f'<p class="vazio">Nenhum resultado para "{html.escape(consulta)}".</p>'
        return sugestao + vazio

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
    blocos = [
        f'<p class="meta">{len(resultado.documentos)} resultado(s){aviso}</p>',
        sugestao,
    ]
    blocos.append(
        _corpo_resultados(resultado.documentos, consulta, disciplina, termos, seccao)
    )
    return "\n".join(bloco for bloco in blocos if bloco)


def _um_resultado(doc, pontuacao, consulta, posicao, termos):
    trecho = _destacar(gerar_trecho(doc.texto, termos), termos)
    etiqueta = (
        f'<span class="disciplina">{html.escape(doc.disciplina)}</span>'
        if doc.disciplina
        else ""
    )
    return (
        f'<div class="resultado" data-id="{doc.id}">'
        f'<p class="titulo">{etiqueta}'
        f'<a href="{html.escape(_ligacao(doc, consulta, posicao))}"'
        ' target="_blank" rel="noopener">'
        f"{html.escape(doc.titulo)}</a>"
        f'<span class="pontuacao">{pontuacao:.4f}</span></p>'
        f'<p class="trecho">{trecho}</p>'
        '<button type="button" class="prever">prever</button>'
        '<div class="pv-inline"></div>'
        "</div>"
    )


def _url(consulta, disciplina, seccao=""):
    parametros = {"q": consulta}
    if disciplina:
        parametros["d"] = disciplina
    if seccao:
        parametros["s"] = seccao
    return "/?" + urlencode(parametros)


def _corpo_resultados(documentos, consulta, disciplina, termos, seccao):
    if seccao:
        escolhidos = mod_seccoes.filtrar(documentos, seccao)
        partes = [
            f'<p class="voltar"><a href="{html.escape(_url(consulta, disciplina))}">'
            "&larr; todos os resultados</a></p>",
            f'<h2 class="sec"><span>{html.escape(mod_seccoes.titulo_da(seccao))}</span>'
            f'<span class="conta">{len(escolhidos)}</span></h2>',
        ]
        partes += [
            _um_resultado(doc, pontuacao, consulta, posicao, termos)
            for posicao, (doc, pontuacao) in enumerate(
                escolhidos[:LIMITE_RESULTADOS], start=1
            )
        ]
        return "\n".join(partes)

    grupos = mod_seccoes.agrupar(documentos)

    if len(grupos) <= 1:
        partes = [
            _um_resultado(doc, pontuacao, consulta, posicao, termos)
            for posicao, (doc, pontuacao) in enumerate(
                documentos[:LIMITE_RESULTADOS], start=1
            )
        ]
        if len(documentos) > LIMITE_RESULTADOS:
            partes.append(
                f'<p class="meta">mostrando {LIMITE_RESULTADOS} de '
                f"{len(documentos)}</p>"
            )
        return "\n".join(partes)

    partes = []
    posicao = 0
    for grupo, itens in grupos:
        if len(itens) > POR_SECCAO:
            direita = (
                f'<a href="{html.escape(_url(consulta, disciplina, grupo.chave))}">'
                f"ver os {len(itens)}</a>"
            )
        else:
            direita = f'<span class="conta">{len(itens)}</span>'
        partes.append(
            f'<h2 class="sec"><span>{html.escape(grupo.titulo)}</span>{direita}</h2>'
        )
        for doc, pontuacao in itens[:POR_SECCAO]:
            posicao += 1
            partes.append(_um_resultado(doc, pontuacao, consulta, posicao, termos))
    return "\n".join(partes)


def _montar_pagina(
    consulta: str, disciplina: str, participante: str,
    corrigida: bool = False, seccao: str = "", exato: bool = False,
) -> str:
    disciplinas: list[str] = []
    if not CAMINHO_BANCO.exists():
        corpo = (
            '<p class="vazio">Indice nao encontrado. '
            "Rode: python main.py indexar &lt;caminho&gt;</p>"
        )
    else:
        conexao = storage.abrir(CAMINHO_BANCO)
        disciplinas = storage.listar_disciplinas(conexao)
        if not consulta and disciplina:
            with uso.abrir() as registo:
                corpo = pagina_disciplina.pagina(conexao, registo, disciplina)
            conexao.close()
            return _MODELO.substitute(
                consulta="",
                opcoes=_opcoes(disciplinas, disciplina),
                novidades=_aviso_novidades(),
                corpo=corpo,
            )
        if consulta:
            resultado = buscar_detalhado(
                conexao, consulta, disciplina or None, permitir_ou=not exato
            )
            with uso.abrir() as registo:
                uso.registar(
                    registo, participante, uso.EVENTO_BUSCA,
                    consulta=consulta,
                    disciplina=disciplina or None,
                    resultados=len(resultado.documentos),
                    modo=resultado.modo,
                )
                if corrigida:
                    uso.registar(
                        registo, participante, uso.EVENTO_SUGESTAO, consulta=consulta
                    )
            corpo = _renderizar(consulta, disciplina, resultado, seccao)
        else:
            corpo = ""
        conexao.close()
    return _MODELO.substitute(
        consulta=html.escape(consulta, quote=True),
        opcoes=_opcoes(disciplinas, disciplina),
        novidades=_aviso_novidades(),
        corpo=corpo,
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
        f'<p class="novo">{quantas} {palavra} nos ultimos'
        f' {novidades.DIAS_RECENTES} dias &middot;'
        f' <a href="/novidades">ver quais</a></p>'
    )


def _disciplinas_disponiveis() -> list[str]:
    if not CAMINHO_BANCO.exists():
        return []
    conexao = storage.abrir(CAMINHO_BANCO)
    try:
        return storage.listar_disciplinas(conexao)
    finally:
        conexao.close()


def _pagina_novidades() -> str:
    recentes = novidades.recentes()
    if not recentes:
        corpo = '<p class="vazio">Nada de novo nos ultimos dias.</p>'
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
        '<p class="voltar"><a href="/">voltar a busca</a></p>'
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
        if _limite_geral.permitir(self._endereco()):
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
                    "Demasiadas tentativas. Tente daqui a 15 minutos."
                ),
                "text/html; charset=utf-8",
            )
            return
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(min(tamanho, 4096)).decode("utf-8", errors="replace")
        codigo = parse_qs(corpo).get("codigo", [""])[0]
        participante = auth.participante_do_codigo(codigo)
        if participante is None:
            self._responder(_pagina_entrada("Codigo invalido."), "text/html; charset=utf-8")
            return
        _limite_entrada.limpar(endereco)
        sessao = auth.criar_sessao(participante, auth.segredo())
        with uso.abrir() as registo:
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
            corpo = _MODELO.substitute(
                consulta="",
                opcoes=_opcoes(_disciplinas_disponiveis(), ""),
                novidades="",
                corpo=_pagina_novidades(),
            )
            self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")
            return
        if url.path == "/estatisticas":
            with uso.abrir() as registo:
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
        corpo = _montar_pagina(
            consulta, disciplina, participante, corrigida, seccao, exato
        )
        self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")

    def _doc_pedido(self, parametros):
        bruto = parametros.get("id", [""])[0]
        if not bruto.isdigit() or not CAMINHO_BANCO.exists():
            return None
        conexao = storage.abrir(CAMINHO_BANCO)
        try:
            documentos = storage.carregar_documentos(conexao, [int(bruto)])
        finally:
            conexao.close()
        return documentos.get(int(bruto))

    def _servir_sugestoes(self, parametros, participante: str) -> None:
        prefixo = parametros.get("q", [""])[0]
        encontradas = []
        if CAMINHO_BANCO.exists():
            indice = storage.abrir(CAMINHO_BANCO)
            try:
                with uso.abrir() as registo:
                    encontradas = sugestoes.sugerir(
                        registo, indice, participante, prefixo
                    )
            finally:
                indice.close()
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
        with uso.abrir() as registo:
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
        with uso.abrir() as registo:
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
        with uso.abrir() as registo:
            uso.registar(
                registo, participante, uso.EVENTO_ABERTURA,
                consulta=parametros.get("q", [""])[0],
                doc_id=doc.id,
                posicao=int(posicao) if posicao.isdigit() else None,
            )
        try:
            dados, nome = _ler_arquivo(doc.origem)
        except (FileNotFoundError, KeyError, PermissionError, zipfile.BadZipFile):
            self.send_error(410, "ficheiro de origem indisponivel")
            return
        tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        self._responder(dados, tipo, nome)

    def _responder(self, corpo: bytes, tipo: str, nome: str | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
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
