import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

AGENTE = "MadalenaBot/0.1 (motor de busca educacional escolar)"
INTERVALO_PADRAO = 1.0
MAX_PAGINAS_PADRAO = 300
PROFUNDIDADE_PADRAO = 3
TEMPO_LIMITE = 15

EXTENSOES_IGNORADAS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".zip", ".mp4", ".mp3", ".woff", ".woff2", ".ttf",
}

MOTIVO_ROBOTS = "bloqueado por robots.txt"
MOTIVO_EXTERNO = "fora do dominio"
MOTIVO_EXTENSAO = "nao e pagina"
MOTIVO_PROFUNDIDADE = "profundidade excedida"
MOTIVO_ERRO = "erro de rede"
MOTIVO_ESTADO = "estado HTTP nao ok"
MOTIVO_TIPO = "tipo nao suportado"

NOME_MANIFESTO = "_origens.json"


@dataclass
class RelatorioRastreio:
    guardadas: int = 0
    pdfs: int = 0
    pedidos: int = 0
    visitadas: set[str] = field(default_factory=set)
    ignoradas: list[tuple[str, str]] = field(default_factory=list)
    profundidade_maxima_atingida: int = 0

    def ignorar(self, url: str, motivo: str) -> None:
        self.ignoradas.append((url, motivo))

    def motivos(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for _, motivo in self.ignoradas:
            contagem[motivo] = contagem.get(motivo, 0) + 1
        return contagem


def normalizar(url: str) -> str:
    partes = urlparse(url)
    caminho = partes.path or "/"
    if caminho != "/" and caminho.endswith("/"):
        caminho = caminho.rstrip("/")
    return urlunparse((partes.scheme, partes.netloc, caminho, "", partes.query, ""))


def nome_ficheiro(url: str, extensao: str = ".html") -> str:
    partes = urlparse(url)
    caminho = partes.path.strip("/")
    if caminho.lower().endswith(extensao):
        caminho = caminho[: -len(extensao)]
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", caminho) or "index"
    marca = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"{base[:70].strip('-')}-{marca}{extensao}"


def _e_pagina(url: str) -> bool:
    sufixo = Path(urlparse(url).path).suffix.lower()
    return sufixo not in EXTENSOES_IGNORADAS


def _carregar_robots(base: str) -> RobotFileParser:
    leitor = RobotFileParser()
    leitor.set_url(urljoin(base, "/robots.txt"))
    try:
        leitor.read()
    except Exception:
        leitor.parse([])
    return leitor


def _urls_do_sitemap(sessao: requests.Session, url: str, vistos: set[str]) -> list[str]:
    if url in vistos:
        return []
    vistos.add(url)
    try:
        resposta = sessao.get(url, timeout=TEMPO_LIMITE)
        if resposta.status_code != 200:
            return []
        raiz = ET.fromstring(resposta.content)
    except (requests.RequestException, ET.ParseError):
        return []

    espaco = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    encontradas: list[str] = []
    for sub in raiz.findall(f"{espaco}sitemap/{espaco}loc"):
        if sub.text:
            encontradas.extend(_urls_do_sitemap(sessao, sub.text.strip(), vistos))
    for item in raiz.findall(f"{espaco}url/{espaco}loc"):
        if item.text:
            encontradas.append(item.text.strip())
    return encontradas


def _guardar_pdf(destino: Path, url: str, dados: bytes) -> str:
    destino.mkdir(parents=True, exist_ok=True)
    nome = nome_ficheiro(url, ".pdf")
    (destino / nome).write_bytes(dados)
    return nome


def _escrever_manifesto(destino: Path, origens: dict[str, str]) -> None:
    if not origens:
        return
    destino.mkdir(parents=True, exist_ok=True)
    (destino / NOME_MANIFESTO).write_text(
        json.dumps(origens, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _guardar(destino: Path, url: str, html: str) -> None:
    marcador = f'<meta name="madalena-origem" content="{url}">'
    if "<head>" in html.lower():
        indice = html.lower().index("<head>") + len("<head>")
        html = html[:indice] + marcador + html[indice:]
    else:
        html = marcador + html
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nome_ficheiro(url)).write_text(html, encoding="utf-8")


def _extrair_ligacoes(html: str, url_atual: str, dominio: str) -> list[str]:
    sopa = BeautifulSoup(html, "html.parser")
    ligacoes = []
    for etiqueta in sopa.find_all("a", href=True):
        destino = normalizar(urljoin(url_atual, etiqueta["href"]))
        if urlparse(destino).netloc == dominio and _e_pagina(destino):
            ligacoes.append(destino)
    return ligacoes


def rastrear(
    url_inicial: str,
    destino: Path,
    max_paginas: int = MAX_PAGINAS_PADRAO,
    profundidade_maxima: int = PROFUNDIDADE_PADRAO,
    intervalo: float = INTERVALO_PADRAO,
    usar_sitemap: bool = True,
    guardar_pdfs: bool = True,
) -> RelatorioRastreio:
    url_inicial = normalizar(url_inicial)
    dominio = urlparse(url_inicial).netloc
    relatorio = RelatorioRastreio()

    sessao = requests.Session()
    sessao.headers["User-Agent"] = AGENTE

    robots = _carregar_robots(url_inicial)
    atraso = robots.crawl_delay(AGENTE)
    if atraso:
        intervalo = max(intervalo, float(atraso))

    fronteira: deque[tuple[str, int]] = deque([(url_inicial, 0)])
    if usar_sitemap:
        for url in _urls_do_sitemap(sessao, urljoin(url_inicial, "/sitemap_index.xml"), set()):
            fronteira.append((normalizar(url), 0))

    ultimo_pedido = 0.0
    origens: dict[str, str] = {}

    while fronteira and relatorio.guardadas < max_paginas:
        url, profundidade = fronteira.popleft()

        if url in relatorio.visitadas:
            continue
        if urlparse(url).netloc != dominio:
            relatorio.ignorar(url, MOTIVO_EXTERNO)
            continue
        if not _e_pagina(url):
            relatorio.ignorar(url, MOTIVO_EXTENSAO)
            continue
        if profundidade > profundidade_maxima:
            relatorio.ignorar(url, MOTIVO_PROFUNDIDADE)
            continue
        if not robots.can_fetch(AGENTE, url):
            relatorio.ignorar(url, MOTIVO_ROBOTS)
            continue

        relatorio.visitadas.add(url)

        espera = intervalo - (time.monotonic() - ultimo_pedido)
        if espera > 0:
            time.sleep(espera)
        ultimo_pedido = time.monotonic()

        try:
            resposta = sessao.get(url, timeout=TEMPO_LIMITE)
            relatorio.pedidos += 1
        except requests.RequestException:
            relatorio.ignorar(url, MOTIVO_ERRO)
            continue

        if resposta.status_code != 200:
            relatorio.ignorar(url, MOTIVO_ESTADO)
            continue

        tipo = resposta.headers.get("Content-Type", "")
        relatorio.profundidade_maxima_atingida = max(
            relatorio.profundidade_maxima_atingida, profundidade
        )

        if "application/pdf" in tipo:
            if not guardar_pdfs:
                relatorio.ignorar(url, MOTIVO_TIPO)
                continue
            origens[_guardar_pdf(destino, url, resposta.content)] = url
            relatorio.guardadas += 1
            relatorio.pdfs += 1
            continue

        if "text/html" not in tipo:
            relatorio.ignorar(url, MOTIVO_TIPO)
            continue

        resposta.encoding = resposta.encoding or "utf-8"
        html = resposta.text
        _guardar(destino, url, html)
        origens[nome_ficheiro(url)] = url
        relatorio.guardadas += 1

        if profundidade < profundidade_maxima:
            for ligacao in _extrair_ligacoes(html, url, dominio):
                if ligacao not in relatorio.visitadas:
                    fronteira.append((ligacao, profundidade + 1))

    _escrever_manifesto(destino, origens)
    return relatorio
