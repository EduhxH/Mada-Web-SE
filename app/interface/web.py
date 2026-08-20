import html
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import parse_qs, urlparse

from app.indexing import storage
from app.indexing.tokenizer import tokenizar
from app.search.query import buscar
from app.search.snippet import gerar_trecho

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
LIMITE_RESULTADOS = 20

_MODELO = Template("""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madalena</title>
<style>
body { font-family: Georgia, "Times New Roman", serif; max-width: 640px; margin: 48px auto; padding: 0 16px; color: #1a1a1a; background: #fdfdfd; }
h1 { font-size: 26px; font-weight: normal; letter-spacing: 2px; margin-bottom: 4px; }
h1 a { color: inherit; text-decoration: none; }
.sub { color: #777; font-size: 13px; margin: 0 0 20px; }
form { margin: 0 0 28px; }
input[type=text] { width: 68%; padding: 8px 10px; font-size: 16px; border: 1px solid #999; background: #fff; font-family: inherit; }
button { padding: 8px 16px; font-size: 15px; border: 1px solid #999; background: #eee; cursor: pointer; font-family: inherit; }
.meta { color: #666; font-size: 13px; margin-bottom: 22px; }
.resultado { margin-bottom: 20px; }
.titulo { font-size: 16px; margin: 0; }
.pontuacao { color: #999; font-size: 12px; margin-left: 6px; }
.trecho { margin: 3px 0 0; font-size: 14px; line-height: 1.5; color: #333; }
.vazio { color: #666; }
footer { margin-top: 48px; border-top: 1px solid #ddd; padding-top: 10px; color: #aaa; font-size: 12px; }
</style>
</head>
<body>
<h1><a href="/">Madalena</a></h1>
<p class="sub">motor de busca educacional</p>
<form action="/" method="get">
<input type="text" name="q" value="$consulta" autofocus>
<button type="submit">buscar</button>
</form>
$corpo
<footer>índice local · sem APIs externas</footer>
</body>
</html>
""")


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


def _renderizar(consulta: str, resultados, duracao_ms: float) -> str:
    if not resultados:
        return f'<p class="vazio">Nenhum resultado para "{html.escape(consulta)}".</p>'
    termos = set(tokenizar(consulta))
    blocos = [
        f'<p class="meta">{len(resultados)} resultado(s) em {duracao_ms:.1f} ms</p>'
    ]
    for doc, pontuacao in resultados[:LIMITE_RESULTADOS]:
        trecho = _destacar(gerar_trecho(doc.texto, termos), termos)
        blocos.append(
            '<div class="resultado">'
            f'<p class="titulo">{html.escape(doc.titulo)}'
            f'<span class="pontuacao">{pontuacao:.4f}</span></p>'
            f'<p class="trecho">{trecho}</p>'
            "</div>"
        )
    if len(resultados) > LIMITE_RESULTADOS:
        blocos.append(
            f'<p class="meta">mostrando {LIMITE_RESULTADOS} de {len(resultados)}</p>'
        )
    return "\n".join(blocos)


def _montar_pagina(consulta: str) -> str:
    if not consulta:
        corpo = ""
    elif not CAMINHO_BANCO.exists():
        corpo = (
            '<p class="vazio">Índice não encontrado. '
            "Rode: python main.py indexar &lt;caminho&gt;</p>"
        )
    else:
        conexao = storage.abrir(CAMINHO_BANCO)
        inicio = time.perf_counter()
        resultados = buscar(conexao, consulta)
        duracao_ms = (time.perf_counter() - inicio) * 1000
        conexao.close()
        corpo = _renderizar(consulta, resultados, duracao_ms)
    return _MODELO.substitute(
        consulta=html.escape(consulta, quote=True), corpo=corpo
    )


class _Manipulador(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path != "/":
            self.send_error(404)
            return
        consulta = parse_qs(url.query).get("q", [""])[0].strip()
        corpo = _montar_pagina(consulta).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


def iniciar(porta: int = 8080) -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), _Manipulador)
    print(f"Madalena no ar em http://127.0.0.1:{porta} (Ctrl+C encerra)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        servidor.server_close()
