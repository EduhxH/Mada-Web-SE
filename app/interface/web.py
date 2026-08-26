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
from app.interface import auth, estatisticas
from app.interface.preview import fragmento, resolver_origem
from app.indexing.tokenizer import tokenizar
from app.search.query import MODO_OU, buscar_detalhado
from app.search.snippet import gerar_trecho

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
RAIZ_DADOS = (Path("data") / "raw").resolve()
LIMITE_RESULTADOS = 20

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
form { margin: 0 0 24px; }
input[type=text] { width: 60%; padding: 8px 10px; font-size: 16px; border: 1px solid #999; background: #fff; font-family: inherit; }
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
  input[type=text], select { width: 100%; max-width: 100%; box-sizing: border-box; margin-bottom: 6px; }
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
<form action="/" method="get">
<input type="text" name="q" value="$consulta" autofocus>
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


def _renderizar(consulta: str, disciplina: str, resultado) -> str:
    sugestao = _bloco_sugestao(resultado, consulta, disciplina)
    if not resultado.documentos:
        vazio = f'<p class="vazio">Nenhum resultado para "{html.escape(consulta)}".</p>'
        return sugestao + vazio

    termos = set(tokenizar(consulta))
    aviso = (
        " &middot; nenhum documento tem todos os termos, "
        "a mostrar correspondencias parciais"
        if resultado.modo == MODO_OU
        else ""
    )
    blocos = [
        f'<p class="meta">{len(resultado.documentos)} resultado(s){aviso}</p>',
        sugestao,
    ]
    for posicao, (doc, pontuacao) in enumerate(
        resultado.documentos[:LIMITE_RESULTADOS], start=1
    ):
        trecho = _destacar(gerar_trecho(doc.texto, termos), termos)
        etiqueta = (
            f'<span class="disciplina">{html.escape(doc.disciplina)}</span>'
            if doc.disciplina
            else ""
        )
        blocos.append(
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
    if len(resultado.documentos) > LIMITE_RESULTADOS:
        blocos.append(
            f'<p class="meta">mostrando {LIMITE_RESULTADOS} de '
            f"{len(resultado.documentos)}</p>"
        )
    return "\n".join(bloco for bloco in blocos if bloco)


def _montar_pagina(
    consulta: str, disciplina: str, participante: str, corrigida: bool = False
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
        if consulta:
            resultado = buscar_detalhado(conexao, consulta, disciplina or None)
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
            corpo = _renderizar(consulta, disciplina, resultado)
        else:
            corpo = ""
        conexao.close()
    return _MODELO.substitute(
        consulta=html.escape(consulta, quote=True),
        opcoes=_opcoes(disciplinas, disciplina),
        corpo=corpo,
    )


class _Manipulador(BaseHTTPRequestHandler):
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
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(min(tamanho, 4096)).decode("utf-8", errors="replace")
        codigo = parse_qs(corpo).get("codigo", [""])[0]
        participante = auth.participante_do_codigo(codigo)
        if participante is None:
            self._responder(_pagina_entrada("Codigo invalido."), "text/html; charset=utf-8")
            return
        sessao = auth.criar_sessao(participante, auth.segredo())
        with uso.abrir() as registo:
            uso.registar(registo, participante, uso.EVENTO_ENTRADA)
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{auth.NOME_COOKIE}={sessao}; Path=/; HttpOnly; SameSite=Lax;"
            f" Max-Age={auth.VALIDADE_DIAS * 86400}",
        )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
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

        if url.path == "/abrir":
            self._redirecionar(parametros, participante)
            return
        if url.path == "/documento":
            self._servir_documento(parametros, participante)
            return
        if url.path == "/preview":
            self._servir_preview(parametros, participante)
            return
        if url.path == "/estatisticas":
            with uso.abrir() as registo:
                corpo = estatisticas.pagina(registo).encode("utf-8")
            self._responder(corpo, "text/html; charset=utf-8")
            return
        if url.path != "/":
            self.send_error(404)
            return

        consulta = parametros.get("q", [""])[0].strip()
        disciplina = parametros.get("d", [""])[0].strip()
        corrigida = parametros.get("corrigida", [""])[0] == "1"
        corpo = _montar_pagina(consulta, disciplina, participante, corrigida)
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
        if nome:
            self.send_header("Content-Disposition", f'inline; filename="{nome}"')
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args) -> None:
        pass


def iniciar(porta: int = 8080, host: str = "127.0.0.1") -> None:
    if not auth.carregar_participantes():
        print("AVISO: nenhum participante criado ainda.")
        print("       python main.py participantes --criar 8")
        print()
    servidor = ThreadingHTTPServer((host, porta), _Manipulador)
    if host != "127.0.0.1":
        print(f"ATENCAO: a aceitar ligacoes de {host} - acesso so por codigo.")
    print(f"Madalena no ar em http://{host}:{porta} (Ctrl+C encerra)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        servidor.server_close()
