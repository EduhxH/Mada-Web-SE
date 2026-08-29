"""Conector do Moodle: sessao autenticada, listagem e descarregamento.

As credenciais vem do ficheiro .env (nunca versionado, nunca no codigo).
A sessao e criada pelo formulario de login do proprio Moodle, incluindo o
logintoken anti-CSRF que ele exige.

Politica: intervalo entre pedidos, so leitura, e nada e publicado nem
alterado. O servidor da escola nao deve dar pela diferenca para um aluno a
navegar.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
# Modulos escritos dentro do proprio Moodle: guardam-se como HTML.
MODULOS_HTML = ("page", "book")

EXTENSOES_ACEITES = {
    ".pdf", ".docx", ".pptx", ".txt", ".md", ".odt", ".ods", ".zip", ".cs",
}

# O Windows recusa nomes terminados em ponto ou espaco, e o Moodle trunca os
# nomes das disciplinas com reticencias na lista.
_PROIBIDOS_EM_NOME = re.compile(r'[<>:"/\\|?*]')


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
        texto = resposta.text.lower()
        if "cookie" in texto and "bloquead" in texto:
            motivo = "cookies bloqueados pelo Moodle"
        raise ErroMoodle(f"Login falhou: {motivo}.")
    return sessao


def sessao_valida(sessao: requests.Session, url_base: str) -> bool:
    pagina = sessao.get(f"{url_base}/my/", timeout=TEMPO_LIMITE)
    if pagina.status_code != 200:
        return False
    return "login/index.php" not in pagina.url


def obter_sesskey(sessao: requests.Session, url_base: str) -> str:
    """O Moodle exige sesskey em algumas accoes, como descarregar uma pasta."""
    pagina = sessao.get(f"{url_base}/my/", timeout=TEMPO_LIMITE)
    casado = re.search(r'"sesskey":"([^"]+)"', pagina.text)
    if casado:
        return casado.group(1)
    casado = re.search(r"sesskey=([A-Za-z0-9]+)", pagina.text)
    return casado.group(1) if casado else ""


def listar_disciplinas(
    sessao: requests.Session, url_base: str
) -> list[tuple[int, str]]:
    """Disciplinas em que o utilizador esta inscrito.

    Os nomes daqui podem vir truncados pelo tema do Moodle; o nome completo
    e lido depois, na propria pagina da disciplina.
    """
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
        nome = ligacao.get("title") or ligacao.get_text(" ", strip=True)
        nome = " ".join(nome.split())
        if nome:
            encontradas.setdefault(int(identificadores[0]), nome)
    return sorted(encontradas.items(), key=lambda par: par[1])


def pagina_da_disciplina(
    sessao: requests.Session, url_base: str, curso: int
) -> tuple[str, list[tuple[str, int, str]]]:
    """(nome completo, recursos) a partir da pagina da disciplina."""
    pagina = sessao.get(
        f"{url_base}/course/view.php?id={curso}", timeout=TEMPO_LIMITE
    )
    sopa = BeautifulSoup(pagina.text, "html.parser")

    nome = ""
    cabecalho = sopa.find("h1")
    if cabecalho:
        nome = " ".join(cabecalho.get_text(" ", strip=True).split())
    if not nome and sopa.title:
        nome = sopa.title.get_text(strip=True).split("|")[0].strip()

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
        texto = " ".join(ligacao.get_text(" ", strip=True).split())
        encontrados.append(
            (modulo, identificador, texto or f"{modulo}-{identificador}")
        )
    return nome, encontrados


def _nome_da_resposta(resposta, alternativa: str) -> str:
    disposicao = resposta.headers.get("Content-Disposition", "")
    casado = re.search(r'filename="?([^";]+)"?', disposicao)
    if casado:
        return casado.group(1)
    caminho = urlparse(resposta.url).path
    # So aceitar o nome do URL se a extensao for de conteudo: um recurso que
    # nao redireciona fica em .../view.php e nao e isso que queremos.
    if caminho and Path(caminho).suffix.lower() in EXTENSOES_ACEITES:
        return Path(caminho).name
    return alternativa


def _registar(relatorio: RelatorioMoodle, disciplina: str, tamanho: int) -> None:
    relatorio.ficheiros += 1
    relatorio.bytes_totais += tamanho
    relatorio.disciplinas[disciplina] = relatorio.disciplinas.get(disciplina, 0) + 1


def _guardar_html(
    resposta,
    alvo: str,
    destino: Path,
    origens: dict[str, str],
    relatorio: RelatorioMoodle,
    disciplina: str,
    alternativa: str,
    titulo: str = "",
) -> None:
    """Uma 'page' ou 'book' do Moodle e material escrito no proprio Moodle."""
    sopa = BeautifulSoup(resposta.text, "html.parser")
    principal = sopa.find("div", {"role": "main"}) or sopa.find("body")
    if principal is None or not principal.get_text(strip=True):
        relatorio.ignorar(alternativa, "pagina sem conteudo")
        return
    marcador = f'<meta name="madalena-origem" content="{alvo}">'
    html = f"<html><head>{marcador}</head><body>{principal}</body></html>"
    destino.mkdir(parents=True, exist_ok=True)
    guardado = nome_ficheiro(alvo, ".html")
    (destino / guardado).write_text(html, encoding="utf-8")
    origens[guardado] = {"url": alvo, "titulo": titulo or alternativa}
    _registar(relatorio, disciplina, len(html))


def _seguir_pluginfile(
    sessao: requests.Session,
    url_base: str,
    modulo: str,
    identificador: int,
    relatorio: RelatorioMoodle,
):
    """Abre a pagina do recurso e descarrega o ficheiro que ela aponta."""
    try:
        pagina = sessao.get(
            f"{url_base}/mod/{modulo}/view.php?id={identificador}",
            timeout=TEMPO_LIMITE,
        )
        relatorio.pedidos += 1
    except requests.RequestException:
        return None
    if pagina.status_code != 200:
        return None

    sopa = BeautifulSoup(pagina.text, "html.parser")
    for ligacao in sopa.find_all("a", href=True):
        if "pluginfile.php" not in ligacao["href"]:
            continue
        try:
            ficheiro = sessao.get(ligacao["href"], timeout=TEMPO_LIMITE)
            relatorio.pedidos += 1
        except requests.RequestException:
            return None
        if ficheiro.status_code == 200:
            return ficheiro
    return None


def descarregar_recurso(
    sessao: requests.Session,
    url_base: str,
    modulo: str,
    identificador: int,
    destino: Path,
    origens: dict[str, str],
    relatorio: RelatorioMoodle,
    disciplina: str,
    sesskey: str = "",
    titulo: str = "",
) -> None:
    rotulo = f"{modulo}-{identificador}"
    if modulo == "folder":
        alvo = f"{url_base}/mod/folder/download_folder.php?id={identificador}"
        if sesskey:
            alvo += f"&sesskey={sesskey}"
    else:
        alvo = f"{url_base}/mod/{modulo}/view.php?id={identificador}&redirect=1"

    try:
        resposta = sessao.get(alvo, timeout=TEMPO_LIMITE, allow_redirects=True)
        relatorio.pedidos += 1
    except requests.RequestException as erro:
        relatorio.ignorar(rotulo, f"erro de rede: {erro}")
        return

    if resposta.status_code != 200 and modulo != "folder":
        # Nem todos os recursos aceitam redirect=1. Abre-se a pagina do
        # recurso e segue-se a ligacao real do ficheiro (pluginfile).
        resposta = _seguir_pluginfile(
            sessao, url_base, modulo, identificador, relatorio
        )
    if resposta is None or resposta.status_code != 200:
        codigo = resposta.status_code if resposta is not None else "sem resposta"
        relatorio.ignorar(rotulo, f"estado HTTP {codigo}")
        return

    tipo = resposta.headers.get("Content-Type", "")
    if "text/html" in tipo:
        if modulo in MODULOS_HTML:
            _guardar_html(
                resposta, alvo, destino, origens, relatorio, disciplina,
                rotulo, titulo,
            )
        else:
            relatorio.ignorar(rotulo, "pagina, nao ficheiro")
        return

    nome = _nome_da_resposta(resposta, f"{rotulo}.bin")
    extensao = Path(nome).suffix.lower()
    if extensao and extensao not in EXTENSOES_ACEITES:
        relatorio.ignorar(nome, f"extensao {extensao} nao aceite")
        return

    destino.mkdir(parents=True, exist_ok=True)
    guardado = nome_ficheiro(f"{alvo}#{nome}", extensao or ".bin")
    (destino / guardado).write_bytes(resposta.content)
    origens[guardado] = {
        "url": f"{url_base}/mod/{modulo}/view.php?id={identificador}",
        "titulo": titulo or Path(nome).stem,
    }
    _registar(relatorio, disciplina, len(resposta.content))


def pasta_da_disciplina(nome: str) -> str:
    """Nome de pasta a partir do titulo da disciplina no Moodle.

    Os titulos vem em formas variadas: "Disciplina de Matematica",
    "Disciplina: PSI9-Arquitetura de Computadores", "PSI9-Ingles". Repete-se
    a limpeza ate estabilizar, porque os prefixos aparecem encadeados.
    Devolve "" quando nao sobra nada util, para quem chama decidir.
    """
    limpo = nome
    for _ in range(3):
        anterior = limpo
        limpo = re.sub(r"^Disciplina\s*(?:de|:)\s*", "", limpo, flags=re.IGNORECASE)
        limpo = re.sub(r"^PSI\d+\s*[-:]\s*", "", limpo)
        limpo = limpo.strip()
        if limpo == anterior:
            break
    limpo = _PROIBIDOS_EM_NOME.sub("-", limpo)
    limpo = limpo.replace("\u2026", "")
    limpo = limpo.strip().strip(". ")
    return limpo[:60].strip().strip(". ")


# nome antigo, mantido para nao partir chamadas existentes
_pasta_da_disciplina = pasta_da_disciplina


def _escrever_manifesto(pasta: Path, origens: dict[str, str]) -> None:
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


def sincronizar(
    raiz: Path,
    disciplinas_pedidas: list[str] | None = None,
    intervalo: float = INTERVALO_PADRAO,
    limite_por_disciplina: int = 0,
    ao_progredir=None,
) -> RelatorioMoodle:
    url_base, utilizador, senha = configuracao()
    sessao = iniciar_sessao(url_base, utilizador, senha)
    sesskey = obter_sesskey(sessao, url_base)
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
    for identificador, nome_curto in todas:
        nome_completo, recursos = pagina_da_disciplina(
            sessao, url_base, identificador
        )
        relatorio.pedidos += 1
        # O h1 e mais fiavel, mas ha disciplinas com titulos inuteis
        # ("Disciplina de ....."): nesse caso vale o nome da lista.
        pasta_nome = pasta_da_disciplina(nome_completo)
        if not pasta_nome:
            pasta_nome = pasta_da_disciplina(nome_curto) or "disciplina"
        nome = pasta_nome
        pasta = raiz / pasta_nome
        origens: dict[str, str] = {}

        if limite_por_disciplina:
            recursos = recursos[:limite_por_disciplina]
        if ao_progredir:
            ao_progredir(nome, len(recursos))

        for modulo, recurso, titulo_recurso in recursos:
            espera = intervalo - (time.monotonic() - ultimo)
            if espera > 0:
                time.sleep(espera)
            ultimo = time.monotonic()
            descarregar_recurso(
                sessao, url_base, modulo, recurso, pasta, origens, relatorio,
                nome, sesskey, titulo_recurso,
            )

        if origens:
            _escrever_manifesto(pasta, origens)

    return relatorio
