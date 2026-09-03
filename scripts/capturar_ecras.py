"""Captura as imagens que ilustram o manual do utilizador.

O problema a resolver: quase todas as paginas que interessam estao atras da
barreira de sessao, e nao ha maneira simples de dar um cookie ao Edge pela
linha de comandos.

A volta e esta: busca-se o HTML com `urllib` e o cookie, grava-se num ficheiro,
e apontam-se os enderecos dos estaticos para o servidor - que **sao publicos**
desde que passaram para antes da barreira. O Edge abre o ficheiro local e
carrega tipos de letra, logotipo e imagens do servidor na mesma. O que se ve na
captura e exactamente o que o aluno ve.

Duas coisas sao retiradas antes de gravar:

- **O guiao das animacoes.** Sem o `anime.js` carregado o guiao sai sozinho e
  nada comeca escondido. Uma captura a meio de uma entrada em cascata mostrava
  meia pagina a 40% de opacidade.
- **O tema do sistema.** Forca-se `data-tema="claro"`: o manual e para imprimir,
  e um fundo preto num PDF gasta tinta e le-se pior em papel.

Correr com o servidor no ar:  python scripts/capturar_ecras.py
"""

from __future__ import annotations

import re
import subprocess
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "assets" / "manual"
TEMPORARIO = DESTINO / "_html"

SERVIDOR = "http://127.0.0.1:8081"
EDGE = Path(
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)

# Escala 2 para as imagens aguentarem impressao sem serrilhado.
ESCALA = 2


def _buscar(caminho: str, cookie: str) -> str:
    pedido = urllib.request.Request(SERVIDOR + caminho)
    if cookie:
        pedido.add_header("Cookie", cookie)
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return resposta.read().decode("utf-8")


def _preparar(html: str, extra_css: str = "", injectar: str = "") -> str:
    """Deixa o HTML pronto para ser aberto de um ficheiro local."""
    # os estaticos vao buscar-se ao servidor
    html = html.replace('src="/estatico/', f'src="{SERVIDOR}/estatico/')
    html = html.replace('href="/estatico/', f'href="{SERVIDOR}/estatico/')
    html = html.replace("url(/estatico/", f"url({SERVIDOR}/estatico/")
    # fora o anime.js: sem ele o guiao sai e nada fica escondido
    html = re.sub(r'<script src="[^"]*anime\.min\.js"[^>]*></script>', "", html)
    # tema claro, para imprimir
    html = html.replace('<html lang="pt-pt">', '<html lang="pt-pt" data-tema="claro">')
    if extra_css:
        html = html.replace("</head>", f"<style>{extra_css}</style></head>")
    if injectar:
        html = html.replace("</body>", f"{injectar}</body>")
    return html


def _capturar(nome: str, html: str, largura: int, altura: int) -> Path:
    TEMPORARIO.mkdir(parents=True, exist_ok=True)
    DESTINO.mkdir(parents=True, exist_ok=True)
    ficheiro = TEMPORARIO / f"{nome}.html"
    ficheiro.write_text(html, encoding="utf-8")
    saida = DESTINO / f"{nome}.png"
    subprocess.run(
        [
            str(EDGE),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            f"--force-device-scale-factor={ESCALA}",
            f"--window-size={largura},{altura}",
            f"--screenshot={saida}",
            "--virtual-time-budget=3000",
            ficheiro.as_uri(),
        ],
        capture_output=True,
        timeout=90,
    )
    return saida


# A lista de sugestoes so aparece depois de se escrever; para a mostrar no
# manual, desenha-se aqui o mesmo HTML que o guiao desenharia.
_SUGESTOES = """
<script>
(function () {
  var campo = document.querySelector("input[name=q]");
  var caixa = document.getElementById("sugestoes");
  if (!campo || !caixa) { return; }
  campo.value = "crit";
  var itens = [
    ["criterios de avaliacao", "ja pesquisou"],
    ["criterios", ""], ["critico", ""], ["critica", ""], ["criticas", ""]
  ];
  caixa.innerHTML = itens.map(function (i, n) {
    return '<div class="' + (n === 0 ? "ativa" : "") + '"><span>' + i[0]
      + '</span><span class="fonte">' + i[1] + '</span></div>';
  }).join("");
  caixa.style.display = "block";
  campo.closest(".campo").classList.add("aberto");
})();
</script>
"""


def main() -> None:
    if not EDGE.exists():
        raise SystemExit(f"Edge nao encontrado em {EDGE}")

    sessao = input("Cookie de sessao (madalena=...): ").strip()

    ecras = [
        # nome, caminho, cookie, largura, altura, css extra, injeccao
        ("entrada", "/", "", 1280, 820, "", ""),
        ("inicial", "/", sessao, 1280, 800, "", ""),
        ("sugestoes", "/", sessao, 1280, 620, "", _SUGESTOES),
        ("resultados", "/?q=criterios+de+avaliacao", sessao, 1400, 900, "", ""),
        ("paginacao", "/?q=criterios+de+avaliacao&pg=3", sessao, 1400, 1750, "", ""),
        ("vazio", "/?q=xpto", sessao, 1280, 620, "", ""),
        ("novidades", "/novidades", sessao, 1280, 620, "", ""),
        ("estatisticas", "/estatisticas", sessao, 1280, 1000, "", ""),
        ("privacidade", "/privacidade", "", 1280, 820, "", ""),
        ("telemovel", "/?q=criterios+de+avaliacao", sessao, 420, 900, "", ""),
    ]

    for nome, caminho, cookie, largura, altura, css, injecta in ecras:
        html = _preparar(_buscar(caminho, cookie), css, injecta)
        saida = _capturar(nome, html, largura, altura)
        if saida.exists():
            print(f"{nome:14s} {largura}x{altura}  {saida.stat().st_size // 1024} KB")
        else:
            print(f"{nome:14s} FALHOU")


if __name__ == "__main__":
    main()
