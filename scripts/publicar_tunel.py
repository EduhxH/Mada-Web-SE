"""Levanta o tunel e mantem um endereco estavel a apontar para ele.

O tunel sem conta recebe um nome aleatorio a cada arranque, o que obrigaria a
avisar toda a gente de cada vez. Aqui o nome aleatorio fica escondido atras de
uma pagina no GitHub Pages, que nunca muda de endereco: publica-se a pagina
com o destino novo e quem tem o link nos favoritos nao da por nada.

Uso:
    python scripts/publicar_tunel.py
    python scripts/publicar_tunel.py --porta 8080 --sem-publicar

A pagina vive num ramo orfao (gh-pages) que so tem o index.html, para nao
misturar o site com o codigo do projeto.
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "scripts" / "pagina_publica.html"
ARVORE = RAIZ / ".gh-pages"
RAMO = "gh-pages"

PADRAO_ENDERECO = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
ESPERA_MAXIMA = 60


def encontrar_cloudflared() -> str:
    """O winget instala fora do PATH de algumas consolas."""
    achado = shutil.which("cloudflared")
    if achado:
        return achado
    for tentativa in (
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ):
        if Path(tentativa).exists():
            return tentativa
    raise SystemExit(
        "cloudflared nao encontrado. Instale com:\n"
        "  winget install --id Cloudflare.cloudflared -e"
    )


def git(*argumentos: str, cwd: Path = RAIZ) -> str:
    resultado = subprocess.run(
        ["git", *argumentos], cwd=cwd, capture_output=True, text=True
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(argumentos)} falhou:\n{resultado.stderr.strip()}"
        )
    return resultado.stdout.strip()


def preparar_arvore() -> None:
    """Cria o ramo orfao e a arvore de trabalho, se ainda nao existirem.

    Uma arvore de trabalho separada evita trocar de ramo no repositorio
    principal, que pode ter alteracoes por guardar.
    """
    if (ARVORE / ".git").exists():
        return

    ramos = git("branch", "--list", RAMO)
    remotos = git("ls-remote", "--heads", "origin", RAMO)

    if ramos:
        git("worktree", "add", str(ARVORE), RAMO)
    elif remotos:
        git("worktree", "add", str(ARVORE), "-b", RAMO, f"origin/{RAMO}")
    else:
        git("worktree", "add", "--detach", str(ARVORE))
        git("checkout", "--orphan", RAMO, cwd=ARVORE)
        git("rm", "-rf", "--quiet", ".", cwd=ARVORE)
        print(f"ramo {RAMO} criado")


def escrever_pagina(endereco: str) -> Path:
    momento = datetime.now().strftime("%d/%m/%Y as %H:%M")
    pagina = (
        MODELO.read_text(encoding="utf-8")
        .replace("__ENDERECO__", endereco)
        .replace("__ATUALIZADO__", momento)
    )
    destino = ARVORE / "index.html"
    destino.write_text(pagina, encoding="utf-8")
    # Sem isto o GitHub Pages passa a pagina pelo Jekyll sem necessidade
    (ARVORE / ".nojekyll").write_text("", encoding="utf-8")
    return destino


def publicar(endereco: str) -> None:
    preparar_arvore()
    escrever_pagina(endereco)
    git("add", "index.html", ".nojekyll", cwd=ARVORE)
    if not git("status", "--porcelain", cwd=ARVORE):
        print("pagina ja apontava para este endereco")
        return
    git("commit", "-m", f"Aponta para {endereco}", cwd=ARVORE)
    git("push", "-u", "origin", RAMO, cwd=ARVORE)
    print("pagina publicada; o GitHub demora cerca de um minuto a servi-la")


def esperar_endereco(processo) -> str:
    """Le a saida do cloudflared ate aparecer o endereco do tunel."""
    limite = time.monotonic() + ESPERA_MAXIMA
    while time.monotonic() < limite:
        linha = processo.stdout.readline()
        if not linha:
            if processo.poll() is not None:
                raise SystemExit("cloudflared terminou antes de dar o endereco")
            continue
        achado = PADRAO_ENDERECO.search(linha)
        if achado:
            return achado.group(0)
    raise SystemExit("o endereco do tunel nao apareceu a tempo")


def main() -> None:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--porta", type=int, default=8080)
    analisador.add_argument(
        "--sem-publicar",
        action="store_true",
        help="mostra o endereco sem tocar no GitHub",
    )
    opcoes = analisador.parse_args()

    executavel = encontrar_cloudflared()
    processo = subprocess.Popen(
        [executavel, "tunnel", "--url", f"http://localhost:{opcoes.porta}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        endereco = esperar_endereco(processo)
        print(f"tunel aberto em {endereco}")

        if opcoes.sem_publicar:
            print("(--sem-publicar: o GitHub nao foi tocado)")
        else:
            publicar(endereco)

        print("Ctrl+C para fechar o tunel.")
        for linha in processo.stdout:
            if "ERR" in linha:
                sys.stderr.write(linha)
    except KeyboardInterrupt:
        print("\na fechar o tunel")
    finally:
        processo.terminate()
        processo.wait(timeout=10)


if __name__ == "__main__":
    main()
