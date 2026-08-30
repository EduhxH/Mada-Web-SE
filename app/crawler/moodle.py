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
from datetime import date
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

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
# "url" ficou de fora: aponta para sites externos, que nao sao conteudo
# da escola e davam a maioria dos 404.
MODULOS_UTEIS = ("resource", "folder", "page", "book")
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
    pastas_vazias: int = 0
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

    # So a regiao de conteudo: blocos e navegacao lateral aparecem em
    # todas as disciplinas e traziam o mesmo recurso 12 vezes.
    conteudo = (
        sopa.find(id="region-main")
        or sopa.find("div", class_="course-content")
        or sopa.find("section", id="region-main")
        or sopa
    )

    encontrados: list[tuple[str, int, str]] = []
    vistos: set[tuple[str, int]] = set()
    for ligacao in conteudo.find_all("a", href=True):
        casado = re.search(r"/mod/([a-z]+)/view\.php\?id=(\d+)", ligacao["href"])
        if not casado:
            continue
        modulo, identificador = casado.group(1), int(casado.group(2))
        if modulo not in MODULOS_UTEIS or (modulo, identificador) in vistos:
            continue
        vistos.add((modulo, identificador))
        texto = _limpar_titulo(ligacao.get_text(" ", strip=True))
        encontrados.append(
            (modulo, identificador, texto or f"{modulo}-{identificador}")
        )
    return nome, encontrados


_ROTULOS_DE_TIPO = (
    "Ficheiro", "Pasta", "Pagina", "Página", "Livro", "URL",
    "File", "Folder", "Page", "Book",
)


def _limpar_titulo(texto: str) -> str:
    """O Moodle acrescenta o tipo ao nome: "Sebenta F5 Ficheiro"."""
    limpo = " ".join(texto.split())
    for rotulo in _ROTULOS_DE_TIPO:
        if limpo.endswith(" " + rotulo):
            limpo = limpo[: -len(rotulo)].strip()
            break
    return limpo


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
    guardado = nome_ficheiro(alvo.split("&")[0], ".html")
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


_PADRAO_PLUGINFILE = re.compile(
    r"""https?://[^"'\s<>]*pluginfile\.php[^"'\s<>]*"""
)


def _ligacoes_de_ficheiro(html: str) -> list[tuple[str, str]]:
    """(url, nome) de cada ficheiro da pagina de uma pasta.

    Procura primeiro nas ligacoes <a>. O Moodle recente desenha a arvore de
    ficheiros por JavaScript, a partir de um JSON embutido: nesse caso nao ha
    <a> nenhum, e os URLs so aparecem no texto em bruto com as barras
    escapadas. Desfaz-se o escape antes de procurar, para o padrao poder ser
    simples.
    """
    sopa = BeautifulSoup(html, "html.parser")
    encontradas: list[tuple[str, str]] = []
    vistas: set[str] = set()

    for ligacao in sopa.find_all("a", href=True):
        endereco = ligacao["href"]
        if "pluginfile.php" not in endereco or endereco in vistas:
            continue
        vistas.add(endereco)
        nome = unquote(Path(urlparse(endereco).path).name)
        rotulo = _limpar_titulo(ligacao.get_text(" ", strip=True))
        encontradas.append((endereco, rotulo or nome))

    if encontradas:
        return encontradas

    sem_escape = html.replace(chr(92) + "/", "/").replace(chr(92) + "u0026", "&")
    for endereco in _PADRAO_PLUGINFILE.findall(sem_escape):
        endereco = endereco.split("?forcedownload")[0]
        if endereco in vistas:
            continue
        vistas.add(endereco)
        nome = unquote(Path(urlparse(endereco).path).name)
        if not nome or not Path(nome).suffix:
            continue
        encontradas.append((endereco, Path(nome).stem))
    return encontradas


def _guardar_bytes(
    conteudo: bytes,
    nome: str,
    chave: str,
    url_publico: str,
    titulo: str,
    destino: Path,
    origens: dict,
    relatorio: RelatorioMoodle,
    disciplina: str,
) -> bool:
    extensao = Path(nome).suffix.lower()
    if extensao and extensao not in EXTENSOES_ACEITES:
        relatorio.ignorar(nome, f"extensao {extensao} nao aceite")
        return False
    destino.mkdir(parents=True, exist_ok=True)
    # A chave do nome nao inclui sesskey nem parametros volateis: o mesmo
    # ficheiro tem de ficar sempre com o mesmo nome entre execucoes.
    guardado = nome_ficheiro(chave, extensao or ".bin")
    (destino / guardado).write_bytes(conteudo)
    origens[guardado] = {"url": url_publico, "titulo": titulo or Path(nome).stem}
    _registar(relatorio, disciplina, len(conteudo))
    return True


def _descarregar_pasta(
    sessao: requests.Session,
    url_base: str,
    identificador: int,
    destino: Path,
    origens: dict,
    relatorio: RelatorioMoodle,
    disciplina: str,
    intervalo: float,
) -> None:
    """Abre a pagina da pasta e descarrega cada ficheiro individualmente.

    O download_folder.php do Moodle e servido por POST com sesskey; seguir os
    ficheiros um a um funciona em qualquer versao e da nomes melhores.
    """
    publico = f"{url_base}/mod/folder/view.php?id={identificador}"
    try:
        pagina = sessao.get(publico, timeout=TEMPO_LIMITE)
        relatorio.pedidos += 1
    except requests.RequestException as erro:
        relatorio.ignorar(f"folder-{identificador}", f"folder: erro de rede {erro}")
        return
    if pagina.status_code != 200:
        relatorio.ignorar(
            f"folder-{identificador}", f"folder: estado HTTP {pagina.status_code}"
        )
        return

    ficheiros = _ligacoes_de_ficheiro(pagina.text)
    if not ficheiros:
        # Uma pasta vazia no Moodle nao e uma falha nossa.
        relatorio.pastas_vazias += 1
        return

    for endereco, titulo in ficheiros:
        time.sleep(intervalo)
        try:
            resposta = sessao.get(endereco, timeout=TEMPO_LIMITE)
            relatorio.pedidos += 1
        except requests.RequestException:
            relatorio.ignorar(titulo, "folder: erro de rede")
            continue
        if resposta.status_code != 200:
            relatorio.ignorar(titulo, f"folder: estado HTTP {resposta.status_code}")
            continue
        nome = _nome_da_resposta(resposta, f"{titulo}.bin")
        # A origem identifica o DOCUMENTO, e o id deriva dela. Sem o nome
        # do ficheiro, todos os ficheiros de uma pasta ficavam com a mesma
        # origem e so o primeiro sobrevivia a indexacao.
        _guardar_bytes(
            resposta.content, nome, f"folder-{identificador}-{nome}",
            f"{publico}#{nome}", titulo, destino, origens, relatorio,
            disciplina,
        )


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
    intervalo: float = INTERVALO_PADRAO,
) -> None:
    rotulo = f"{modulo}-{identificador}"

    if modulo == "folder":
        _descarregar_pasta(
            sessao, url_base, identificador, destino, origens, relatorio,
            disciplina, intervalo,
        )
        return

    publico = f"{url_base}/mod/{modulo}/view.php?id={identificador}"
    try:
        resposta = sessao.get(
            f"{publico}&redirect=1", timeout=TEMPO_LIMITE, allow_redirects=True
        )
        relatorio.pedidos += 1
    except requests.RequestException as erro:
        relatorio.ignorar(rotulo, f"{modulo}: erro de rede {erro}")
        return

    if resposta.status_code != 200:
        resposta = _seguir_pluginfile(
            sessao, url_base, modulo, identificador, relatorio
        )
    if resposta is None or resposta.status_code != 200:
        codigo = resposta.status_code if resposta is not None else "sem resposta"
        relatorio.ignorar(rotulo, f"{modulo}: estado HTTP {codigo}")
        return

    tipo = resposta.headers.get("Content-Type", "")
    if "text/html" in tipo:
        if modulo in MODULOS_HTML:
            _guardar_html(
                resposta, publico, destino, origens, relatorio, disciplina,
                rotulo, titulo,
            )
        else:
            relatorio.ignorar(rotulo, f"{modulo}: pagina, nao ficheiro")
        return

    nome = _nome_da_resposta(resposta, f"{rotulo}.bin")
    _guardar_bytes(
        resposta.content, nome, f"{modulo}-{identificador}-{nome}",
        publico, titulo, destino, origens, relatorio, disciplina,
    )


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


_PADRAO_MODULO = re.compile(r"view\.php\?id=(\d+)")


@dataclass(frozen=True)
class ModuloNovo:
    """Um modulo que esta no Moodle e ainda nao esta ca."""

    disciplina: str
    modulo: str
    identificador: int
    titulo: str

    @property
    def url(self) -> str:
        return f"/mod/{self.modulo}/view.php?id={self.identificador}"


NOME_VISTOS = "_modulos_vistos.json"


def modulos_com_ficheiros(raiz: Path) -> set[int]:
    """Modulos que produziram pelo menos um ficheiro, lidos dos manifestos.

    O manifesto guarda o URL de origem de cada ficheiro, e o identificador do
    modulo vem la dentro. Serve de memoria entre execucoes sem precisar de
    outra base de dados.
    """
    conhecidos: set[int] = set()
    for manifesto in raiz.rglob(NOME_MANIFESTO):
        try:
            registos = json.loads(manifesto.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for valor in registos.values():
            url = valor.get("url", "") if isinstance(valor, dict) else valor
            casado = _PADRAO_MODULO.search(url or "")
            if casado:
                conhecidos.add(int(casado.group(1)))
    return conhecidos


def modulos_vistos(raiz: Path) -> set[int]:
    """Modulos que ja examinamos, tenham dado ficheiro ou nao.

    Sem isto, um modulo esteril - pasta vazia, ligacao morta, formato que nao
    lemos - ficava para sempre por baixar e seria anunciado como novidade
    todos os dias. Sao a maioria: das centenas anunciadas pelo Moodle, so uma
    fracao tem mesmo ficheiro por tras.

    A sincronizacao completa volta a tentar tudo, portanto uma pasta que
    entretanto se encha nao fica perdida.
    """
    caminho = raiz / NOME_VISTOS
    if not caminho.exists():
        return set()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    if not isinstance(dados, dict):
        return set()
    return {int(chave) for chave in dados if str(chave).isdigit()}


def marcar_vistos(raiz: Path, identificadores: set[int]) -> None:
    """Guarda os modulos examinados, com a data em que o foram."""
    if not identificadores:
        return
    caminho = raiz / NOME_VISTOS
    registo: dict[str, str] = {}
    if caminho.exists():
        try:
            lido = json.loads(caminho.read_text(encoding="utf-8"))
            if isinstance(lido, dict):
                registo = {str(k): str(v) for k, v in lido.items()}
        except (json.JSONDecodeError, OSError):
            registo = {}
    hoje = date.today().isoformat()
    for identificador in identificadores:
        registo.setdefault(str(identificador), hoje)
    raiz.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(registo, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def modulos_conhecidos(raiz: Path) -> set[int]:
    """Tudo o que ja passou por ca: com ficheiro ou examinado sem resultado."""
    return modulos_com_ficheiros(raiz) | modulos_vistos(raiz)


def verificar(
    raiz: Path,
    disciplinas_pedidas: list[str] | None = None,
    intervalo: float = INTERVALO_PADRAO,
) -> tuple[list[ModuloNovo], int]:
    """Procura material novo sem descarregar nada.

    Um pedido por disciplina, contra as centenas de uma sincronizacao
    completa. Compara os modulos anunciados na pagina com os que ja temos.

    Repare-se no que isto NAO ve: um professor que substitua o ficheiro
    dentro de um recurso existente mantem o mesmo identificador, e portanto
    passa despercebido aqui. Essa mudanca so aparece ao descarregar, e e o
    reindexar que a deteta pela impressao digital do conteudo.

    Devolve (novidades, total de modulos vistos).
    """
    url_base, utilizador, senha = configuracao()
    sessao = iniciar_sessao(url_base, utilizador, senha)
    conhecidos = modulos_conhecidos(raiz)

    todas = _filtrar_disciplinas(
        listar_disciplinas(sessao, url_base), disciplinas_pedidas
    )

    novidades: list[ModuloNovo] = []
    vistos = 0
    ultimo = 0.0
    for identificador, nome_curto in todas:
        espera = intervalo - (time.monotonic() - ultimo)
        if espera > 0:
            time.sleep(espera)
        ultimo = time.monotonic()

        nome_completo, recursos = pagina_da_disciplina(
            sessao, url_base, identificador
        )
        disciplina = (
            pasta_da_disciplina(nome_completo)
            or pasta_da_disciplina(nome_curto)
            or "disciplina"
        )
        vistos += len(recursos)
        for modulo, recurso, titulo in recursos:
            if recurso not in conhecidos:
                novidades.append(ModuloNovo(disciplina, modulo, recurso, titulo))
    return novidades, vistos


def _filtrar_disciplinas(todas, pedidas: list[str] | None):
    if not pedidas:
        return todas
    procurados = [d.lower() for d in pedidas]
    return [
        (identificador, nome)
        for identificador, nome in todas
        if any(p in nome.lower() for p in procurados)
    ]


def sincronizar(
    raiz: Path,
    disciplinas_pedidas: list[str] | None = None,
    intervalo: float = INTERVALO_PADRAO,
    limite_por_disciplina: int = 0,
    ao_progredir=None,
    apenas: set[int] | None = None,
) -> RelatorioMoodle:
    url_base, utilizador, senha = configuracao()
    sessao = iniciar_sessao(url_base, utilizador, senha)
    sesskey = obter_sesskey(sessao, url_base)
    relatorio = RelatorioMoodle()

    todas = _filtrar_disciplinas(
        listar_disciplinas(sessao, url_base), disciplinas_pedidas
    )

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

        # Sincronizacao incremental: os manifestos juntam-se em vez de se
        # substituirem, por isso saltar o que ja ca esta nao apaga registo.
        if apenas is not None:
            recursos = [r for r in recursos if r[1] in apenas]
        if limite_por_disciplina:
            recursos = recursos[:limite_por_disciplina]
        if ao_progredir:
            ao_progredir(nome, len(recursos))
        if not recursos:
            continue

        for modulo, recurso, titulo_recurso in recursos:
            espera = intervalo - (time.monotonic() - ultimo)
            if espera > 0:
                time.sleep(espera)
            ultimo = time.monotonic()
            descarregar_recurso(
                sessao, url_base, modulo, recurso, pasta, origens, relatorio,
                nome, sesskey, titulo_recurso, intervalo,
            )

        if origens:
            _escrever_manifesto(pasta, origens)

    return relatorio


def diagnosticar_pasta(guardar_em: Path | None = None, quantas: int = 6) -> None:
    """Inspeciona varias pastas reais e diz quantos ficheiros cada uma tem.

    Existe porque adivinhar a estrutura do HTML do Moodle custa uma execucao
    de 7 minutos por tentativa.
    """
    url_base, utilizador, senha = configuracao()
    sessao = iniciar_sessao(url_base, utilizador, senha)
    print(f"Sessao iniciada como {utilizador}.")
    print()

    vistas = 0
    com_conteudo = 0
    for identificador, nome in listar_disciplinas(sessao, url_base):
        _, recursos = pagina_da_disciplina(sessao, url_base, identificador)
        for modulo, recurso, titulo in recursos:
            if modulo != "folder" or vistas >= quantas:
                continue
            vistas += 1
            publico = f"{url_base}/mod/folder/view.php?id={recurso}"
            pagina = sessao.get(publico, timeout=TEMPO_LIMITE)
            html = pagina.text

            ficheiros = _ligacoes_de_ficheiro(html)
            nomes_vazios = html.count('<span class="fp-filename"></span>')
            nomes_cheios = html.count('class="fp-filename">') - nomes_vazios
            if ficheiros:
                com_conteudo += 1

            print(f"{nome[:26]:<28} {titulo[:26]:<28} id {recurso}")
            print(
                f"   estado {pagina.status_code}"
                f" | pluginfile: {html.count('pluginfile.php')}"
                f" | fp-filename vazios: {nomes_vazios}"
                f" | com nome: {max(nomes_cheios, 0)}"
                f" | extraidos: {len(ficheiros)}"
            )
            for endereco, rotulo in ficheiros[:2]:
                print(f"     - {rotulo[:30]:<32} {endereco[:58]}")
            if guardar_em and vistas == 1:
                guardar_em.parent.mkdir(parents=True, exist_ok=True)
                guardar_em.write_text(html, encoding="utf-8")
        if vistas >= quantas:
            break

    print()
    print(f"{vistas} pastas inspecionadas, {com_conteudo} com ficheiros extraidos.")
    if guardar_em:
        print(f"HTML da primeira em {guardar_em}")
