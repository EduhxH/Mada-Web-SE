"""Encontra em disco a copia do documento que o indice descreve.

Existe porque o Moodle nao deixa ler o que guarda. Medido: um ficheiro dentro
de uma pasta do Moodle vem com `Content-Disposition: attachment`, ou seja o
browser e instruido a descarregar em vez de mostrar; e sem sessao iniciada no
Moodle o mesmo endereco atira para a pagina de entrada. Pior ainda, o endereco
que o indice guarda para esses 625 documentos e o da **pasta**, nao o do
ficheiro: quem clica aterra numa listagem e tem de procurar o documento a mao,
perdendo o numero da pagina que a busca tinha acertado.

Servir a nossa propria copia resolve as tres coisas de uma vez - abre no
browser, abre na pagina certa, e nao exige sessao no Moodle. E resolve uma
quarta que nao era obvia: o que o aluno le passa a ser exactamente o texto que
foi indexado. Enquanto o link ia para fora, o ficheiro podia ter sido
substituido e o numero de pagina deixava de bater certo - foi assim que o
horario da PSI9 passou semanas a apontar para outra turma.

**A fonte continua nomeada.** Cada resultado leva ao lado uma ligacao para o
original no Moodle ou no site. O que muda e qual das duas e a accao principal.

**As paginas HTML do site nao entram.** Uma pagina do sefo.pt servida daqui
perdia o estilo, os menus e as imagens, e nao ha problema nenhum a resolver:
essas abrem bem no browser e nao descarregam nada. Serve-se o que e ficheiro -
PDF, docx, pptx - e liga-se ao que e pagina.
"""

import json
import threading
import time
from pathlib import Path

RAIZ_DADOS = (Path("data") / "raw").resolve()

# Extensoes que se servem daqui. As paginas ficam de fora de proposito: ver o
# cabecalho. O `.zip` tambem - um ZIP e para descarregar de qualquer maneira, e
# o que interessa dele ja foi extraido.
SERVIVEIS = {".pdf", ".docx", ".pptx", ".odt", ".ods", ".txt", ".md", ".cs"}

# Acima disto nao se serve: manda-se para a origem. Ha um PDF de 117 MB neste
# corpus, e para um aluno no telemovel isso e mau venha de onde vier - mas vindo
# de ca passa tambem pelo tunel gratuito e pela ligacao de casa do Eduardo, que
# e o elo mais fraco dos dois. O servidor da escola aguenta melhor esse peso.
#
# Trinta megabytes cobrem 142 dos 143 ficheiros. O tecto existe para o caso
# extremo, nao para o comum.
LIMITE_SERVIR = 30 * 1024 * 1024

_cache: tuple[object, dict[str, Path]] | None = None
_proxima_verificacao = 0.0
_tranca = threading.Lock()

# De quanto em quanto tempo se volta a perguntar ao disco se os manifestos
# mudaram. Perguntar sempre custava 5,5 ms - uma travessia de `data/raw`, que
# tem milhares de ficheiros - e isto e chamado uma vez por resultado, dez vezes
# por pagina. Meio segundo por busca so para confirmar o que muda tres vezes por
# dia. Trinta segundos de atraso a ver material novo nao se nota; 55 ms por
# pagina notam-se.
SEGUNDOS_ENTRE_VERIFICACOES = 30


def _sem_pagina(origem: str) -> str:
    """A origem sem o `#pagina=N` final, que e como o manifesto a guarda.

    Cuidado com o `#`: ha duas ancoras. Um ficheiro dentro de uma pasta do
    Moodle e `.../view.php?id=82783#Ficheiro.pdf#pagina=8`, e so a ultima e que
    se tira. Partir no primeiro `#` juntava todos os ficheiros de uma pasta no
    mesmo documento.
    """
    marca = "#pagina="
    if marca in origem:
        antes, depois = origem.rsplit(marca, 1)
        if depois.isdigit():
            return antes
    marca = "#slide="
    if marca in origem:
        antes, depois = origem.rsplit(marca, 1)
        if depois.isdigit():
            return antes
    return origem


def pagina_de(origem: str) -> int | None:
    """O numero de pagina que a origem carrega, se carregar algum."""
    for marca in ("#pagina=", "#slide="):
        if marca in origem:
            _, depois = origem.rsplit(marca, 1)
            if depois.isdigit():
                return int(depois)
    return None


def _marca_dos_manifestos() -> tuple:
    """Chave de cache: que manifestos existem e quando mudaram.

    Os manifestos sao reescritos quando o rastreio ou o conector correm, o que
    acontece tres vezes por dia num processo a parte. Sem isto, um servidor a
    correr desde a manha continuaria a nao encontrar o que entrou a tarde.
    """
    marcas = []
    try:
        for manifesto in sorted(RAIZ_DADOS.rglob("_origens.json")):
            estado = manifesto.stat()
            marcas.append((str(manifesto), estado.st_mtime_ns, estado.st_size))
    except OSError:
        pass
    return tuple(marcas)


def _mapa() -> dict[str, Path]:
    """origem -> ficheiro local, construido a partir dos manifestos."""
    global _cache, _proxima_verificacao
    agora = time.monotonic()
    with _tranca:
        if _cache is not None and agora < _proxima_verificacao:
            return _cache[1]

    marca = _marca_dos_manifestos()
    with _tranca:
        _proxima_verificacao = agora + SEGUNDOS_ENTRE_VERIFICACOES
        if _cache is not None and _cache[0] == marca:
            return _cache[1]

    mapa: dict[str, Path] = {}
    for manifesto in RAIZ_DADOS.rglob("_origens.json"):
        try:
            dados = json.loads(manifesto.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(dados, dict):
            continue
        for nome, registo in dados.items():
            url = registo if isinstance(registo, str) else (registo or {}).get("url")
            if not url or not isinstance(url, str):
                continue
            alvo = manifesto.parent / nome
            try:
                resolvido = alvo.resolve()
            except OSError:
                continue
            # O manifesto e um ficheiro em disco como outro qualquer. Nao se
            # confia nele para sair da raiz de dados.
            if not resolvido.is_relative_to(RAIZ_DADOS) or not resolvido.is_file():
                continue
            mapa[url] = resolvido

    with _tranca:
        _cache = (marca, mapa)
    return mapa


def caminho_de(origem: str) -> Path | None:
    """O ficheiro em disco desta origem, ou None se nao ha ou nao se serve."""
    if not origem:
        return None
    alvo = _mapa().get(_sem_pagina(origem))
    if alvo is None:
        return None
    if alvo.suffix.lower() not in SERVIVEIS:
        return None
    try:
        if alvo.stat().st_size > LIMITE_SERVIR:
            return None
    except OSError:
        return None
    return alvo


def ha_copia(origem: str) -> bool:
    return caminho_de(origem) is not None


def esquecer_cache() -> None:
    """Para os testes, e para quando os manifestos mudam debaixo dos pes."""
    global _cache, _proxima_verificacao
    with _tranca:
        _cache = None
        _proxima_verificacao = 0.0
