"""Conector do Moodle: sessao autenticada, listagem e descarregamento.

As credenciais vem do ficheiro .env (nunca versionado, nunca no codigo).
A sessao e criada pelo formulario de login do proprio Moodle, incluindo o
logintoken anti-CSRF que ele exige.

Politica: intervalo entre pedidos, so leitura, e nada e publicado nem
alterado. O servidor da escola nao deve dar pela diferenca para um aluno a
navegar.
"""

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.crawler.web_source import NOME_MANIFESTO, nome_ficheiro
from app.interface.auth import carregar_env

AGENTE = "MadalenaBot/0.1 (projeto escolar; sincronizacao de materiais)"
INTERVALO_PADRAO = 1.0
TEMPO_LIMITE = 30

VAR_URL = "MOODLE_URL"
VAR_UTILIZADOR = "MOODLE_UTILIZADOR"
VAR_SENHA = "MOODLE_SENHA"

# Modulos que contem material para indexar. Foruns, questionarios e chats
# ficam de fora: sao conversas e avaliacoes, nao material de estudo.
MODULOS_UTEIS = ("resource", "folder", "page", "book", "url")

EXTENSOES_ACEITES = {
    ".pdf", ".docx", ".pptx", ".txt", ".md", ".odt", ".ods", ".zip", ".cs",
}


class ErroMoodle(RuntimeError):
    pass


@dataclass
class RelatorioMoodle:
    disciplinas: dict[str, int] = field(default_factory=dict)
    ficheiros: int = 0
    bytes_totais: int = 0
    pedidos: int = 0
    ignorados: list[tuple[str, str]] = field(default_factory=list)

    def ignorar(self, nome: str, motivo: str) -> None:
        self.ignorados.append((nome, motivo))


def configuracao() -> tuple[str, str, str]:
    carregar_env()
    url = os.environ.get(VAR_URL, "").strip().rstrip("/")
    utilizador = os.environ.get(VAR_UTILIZADOR, "").strip()
    senha = os.environ.get(VAR_SENHA, "")
    if not (url and utilizador and senha):
        raise ErroMoodle(
            "Faltam credenciais. Crie um ficheiro .env na raiz do projeto com:\n"
            f"  {VAR_URL}=https://moodle.sefo.pt\n"
            f"  {VAR_UTILIZADOR}=o_seu_utilizador\n"
            f"  {VAR_SENHA}=a_sua_senha\n"
            "O .env esta no .gitignore e nunca e versionado."
        )
    return url, utilizador, senha


def iniciar_sessao(url_base: str, utilizador: str, senha: str) -> requests.Session:
    """Faz login pelo formulario do Moodle, com o logintoken anti-CSRF."""
    sessao = requests.Session()
    sessao.headers["User-Agent"] = AGENTE

    entrada = f"{url_base}/login/index.php"
    pagina = sessao.get(entrada, timeout=TEMPO_LIMITE)
    sopa = BeautifulSoup(pagina.text, "html.parser")

    campo = sopa.find("input", {"name": "logintoken"})
    dados = {"username": utilizador, "password": senha}
    if campo and campo.get("value"):
        dados["logintoken"] = campo["value"]

    resposta = sessao.post(entrada, data=dados, timeout=TEMPO_LIMITE)
    if not sessao_valida(sessao, url_base):
        motivo = "credenciais recusadas"
        if "cookies" in resposta.text.lower() and "bloquead" in resposta.text.lower():
            motivo = "cookies bloqueados pelo Moodle"
        raise ErroMoodle(f"Login falhou: {motivo}.")
    return sessao


def sessao_valida(sessao: requests.Session, url_base: str) -> bool:
    pagina = sessao.get(f"{url_base}/my/", timeout=TEMPO_LIMITE)
    if pagina.status_code != 200:
        return False
    return "login/index.php" not in pagina.url


def listar_disciplinas(
    sessao: requests.Session, url_base: str
) -> list[tuple[int, str]]:
    """Disciplinas em que o utilizador esta inscrito."""
    pagina = sessao.get(f"{url_base}/my/courses.php", timeout=TEMPO_LIMITE)
    if pagina.status_code != 200:
        pagina = sessao.get(f"{url_base}/my/", timeout=TEMPO_LIMITE)

    sopa = BeautifulSoup(pagina.text, "html.parser")
    encontradas: dict[int, str] = {}
    for ligacao in sopa.find_all("a", href=True):
        if "/course/view.php" not in ligacao["href"]:
            continue
        parametros = parse_qs(urlparse(ligacao["href"]).query)
        identificadores = parametros.get("id")
        if not identificadores or not identificadores[0].isdigit():
            continue
        nome = " ".join(ligacao.get_text(" ", strip=True).split())
        if nome:
            encontradas.setdefault(int(identificadores[0]), nome)
    return sorted(encontradas.items(), key=lambda par: par[1])


def recursos_da_disciplina(
    sessao: requests.Session, url_base: str, curso: int
) -> list[tuple[str, int, str]]:
    """(modulo, id, nome) de cada recurso da pagina da disciplina."""
    pagina = sessao.get(
        f"{url_base}/course/view.php?id={curso}", timeout=TEMPO_LIMITE
    )
    sopa = BeautifulSoup(pagina.text, "html.parser")
    encontrados: list[tuple[str, int, str]] = []
    vistos: set[tuple[str, int]] = set()

    for ligacao in sopa.find_all("a", href=True):
        casado = re.search(r"/mod/([a-z]+)/view\.php\?id=(\d+)", ligacao["href"])
        if not casado:
            continue
        modulo, identificador = casado.group(1), int(casado.group(2))
        if modulo not in MODULOS_UTEIS or (modulo, identificador) in vistos:
            continue
        vistos.add((modulo, identificador))
        nome = " ".join(ligacao.get_text(" ", strip=True).split())
        encontrados.append((modulo, identificador, nome or f"{modulo}-{identificador}"))
    return encontrados


def _nome_da_resposta(resposta: requests.Response, alternativa: str) -> str:
    disposicao = resposta.headers.get("Content-Disposition", "")
    casado = re.search(r'filename="?([^";]+)"?', disposicao)
    if casado:
        return casado.group(1)
    caminho = urlparse(resposta.url).path
    # So aceitar o nome do URL se a extensao for de conteudo: um recurso
    # que nao redireciona fica em .../view.php e nao e isso que queremos.
    if caminho and Path(caminho).suffix.lower() in EXTENSOES_ACEITES:
        return Path(caminho).name
    return alternativa


def descarregar_recurso(
    sessao: requests.Session,
    url_base: str,
    modulo: str,
    identificador: int,
    destino: Path,
    origens: dict[str, str],
    relatorio: RelatorioMoodle,
    disciplina: str,
) -> None:
    if modulo == "folder":
        alvo = f"{url_base}/mod/folder/download_folder.php?id={identificador}"
    else:
        alvo = f"{url_base}/mod/{modulo}/view.php?id={identificador}&redirect=1"

    try:
        resposta = sessao.get(alvo, timeout=TEMPO_LIMITE, allow_redirects=True)
        relatorio.pedidos += 1
    except requests.RequestException as erro:
        relatorio.ignorar(f"{modulo}-{identificador}", f"erro de rede: {erro}")
        return

    if resposta.status_code != 200:
        relatorio.ignorar(
            f"{modulo}-{identificador}", f"estado HTTP {resposta.status_code}"
        )
        return

    tipo = resposta.headers.get("Content-Type", "")
    if "text/html" in tipo:
        relatorio.ignorar(f"{modulo}-{identificador}", "pagina, nao ficheiro")
        return

    nome = _nome_da_resposta(resposta, f"{modulo}-{identificador}.bin")
    extensao = Path(nome).suffix.lower()
    if extensao and extensao not in EXTENSOES_ACEITES:
        relatorio.ignorar(nome, f"extensao {extensao} nao aceite")
        return

    destino.mkdir(parents=True, exist_ok=True)
    guardado = nome_ficheiro(
        f"{alvo}#{nome}", extensao or ".bin"
    )
    (destino / guardado).write_bytes(resposta.content)
    origens[guardado] = f"{url_base}/mod/{modulo}/view.php?id={identificador}"

    relatorio.ficheiros += 1
    relatorio.bytes_totais += len(resposta.content)
    relatorio.disciplinas[disciplina] = relatorio.disciplinas.get(disciplina, 0) + 1


def sincronizar(
    raiz: Path,
    disciplinas_pedidas: list[str] | None = None,
    intervalo: float = INTERVALO_PADRAO,
    limite_por_disciplina: int = 0,
    ao_progredir=None,
) -> RelatorioMoodle:
    url_base, utilizador, senha = configuracao()
    sessao = iniciar_sessao(url_base, utilizador, senha)
    relatorio = RelatorioMoodle()

    todas = listar_disciplinas(sessao, url_base)
    if disciplinas_pedidas:
        procurados = [d.lower() for d in disciplinas_pedidas]
        todas = [
            (identificador, nome)
            for identificador, nome in todas
            if any(p in nome.lower() for p in procurados)
        ]

    ultimo = 0.0
    for identificador, nome in todas:
        pasta = raiz / _pasta_da_disciplina(nome)
        origens: dict[str, str] = {}
        recursos = recursos_da_disciplina(sessao, url_base, identificador)
        relatorio.pedidos += 1
        if limite_por_disciplina:
            recursos = recursos[:limite_por_disciplina]

        if ao_progredir:
            ao_progredir(nome, len(recursos))

        for modulo, recurso, _ in recursos:
            espera = intervalo - (time.monotonic() - ultimo)
            if espera > 0:
                time.sleep(espera)
            ultimo = time.monotonic()
            descarregar_recurso(
                sessao, url_base, modulo, recurso, pasta, origens, relatorio, nome
            )

        if origens:
            _escrever_manifesto(pasta, origens)

    return relatorio


def _pasta_da_disciplina(nome: str) -> str:
    limpo = re.sub(r"^PSI\d+\s*[-:]\s*", "", nome)
    limpo = re.sub(r"^Disciplina de\s+", "", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r'[<>:"/\\|?*]', "-", limpo).strip()
    return limpo[:60] or nome[:60]


def _escrever_manifesto(pasta: Path, origens: dict[str, str]) -> None:
    import json

    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / NOME_MANIFESTO
    existentes: dict[str, str] = {}
    if caminho.exists():
        try:
            existentes = json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existentes = {}
    existentes.update(origens)
    caminho.write_text(
        json.dumps(existentes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
