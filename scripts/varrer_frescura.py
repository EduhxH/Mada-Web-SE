"""Procura no indice documentos cuja origem ja mudou desde que foram apanhados.

Nasceu de um caso concreto. O horario da escola vive num endereco fixo e e
substituido todas as semanas; o indice tinha a versao de julho, em que a turma
PSI9 estava nas paginas 11 e 12. A busca respondia "pagina 11", o link abria o
PDF **ao vivo** nessa pagina - e na versao de agora a pagina 11 e outra turma.
O resultado estava certo em relacao ao que o indice sabia e errado em relacao ao
que o aluno via.

Isto e pior do que um documento simplesmente desactualizado, porque nao ha nada
no ecra que denuncie o problema: o titulo bate certo, o trecho bate certo, e so
quem conhece o documento e que percebe que abriu a pagina errada. Um documento
que desaparece da uma pagina de erro e toda a gente entende; este mente em
silencio.

O que se verifica, por ficheiro e nao por pagina:

    mudou      o servidor diz que o ficheiro e mais recente do que a nossa
               copia, ou que tem outro tamanho
    sumiu      o endereco ja nao responde
    fresco     a copia local continua a valer

Os que mudam **e** tem ancora de pagina (`#pagina=N`) sao os graves, e aparecem
primeiro: ai o numero da pagina que o indice guarda deixa de corresponder ao
ficheiro que o aluno abre.

    python scripts/varrer_frescura.py                # tudo
    python scripts/varrer_frescura.py --so-ancoradas # so as que derivam paginas
    python scripts/varrer_frescura.py --intervalo 2

Um pedido HEAD por ficheiro, com intervalo, porque isto bate no servidor da
escola. Nao descarrega nada.
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import requests

from app.crawler import moodle
from app.indexing import storage

CAMINHO_BANCO = Path("data") / "indice.sqlite3"
RAIZ_DADOS = Path("data") / "raw"
TEMPO_LIMITE = 25

MUDOU, SUMIU, FRESCO = "mudou", "sumiu", "fresco"
SEM_RESPOSTA = "sem resposta"
# Distinto de `SEM_RESPOSTA`: aqui o servidor respondeu bem, mas nao mandou nem
# `Last-Modified` nem `Content-Length`, e sem um deles nao ha como comparar.
# Acontece em tudo o que e gerado na hora - as paginas do WordPress da escola e
# as vistas de pasta do Moodle. Nao e um defeito do indice, e o alcance desta
# ferramenta: dos 326 enderecos, 58 sao ficheiros estaticos e dao validadores.
NAO_VERIFICAVEL = "nao verificavel"


# Ha DUAS convencoes de ancora nas origens, e confundi-las foi o primeiro erro
# desta varredura:
#
#   .../horarios.pdf#pagina=27                      pagina dentro de um PDF
#   .../view.php?id=82783#Ficheiro.pdf#pagina=8     ficheiro dentro de uma pasta
#                                                   do Moodle, e depois a pagina
#
# Partir no primeiro `#` juntava num so "ficheiro" todos os PDF de uma pasta - e
# por isso uma pasta aparecia com 140 paginas e nao havia copia local nenhuma
# que lhe correspondesse.
_ANCORA_PAGINA = re.compile(r"#pagina=\d+$")


def _ficheiro_de(origem: str) -> str:
    """A identidade do ficheiro: tudo menos o numero da pagina."""
    return _ANCORA_PAGINA.sub("", origem)


def _pedivel(origem: str) -> str:
    """O endereco que se manda ao servidor - sem ancora nenhuma.

    O fragmento nunca viaja num pedido HTTP; serve so para o browser. Mandar a
    pasta e o que se quer: e ela que diz se mudou.
    """
    return _ficheiro_de(origem).split("#")[0]


def mapa_local() -> dict[str, Path]:
    """endereco pedivel -> o ficheiro local mais recente que veio de la.

    Guarda-se o mais recente e nao um qualquer porque uma pasta do Moodle da
    varios ficheiros: se o servidor diz que a pasta e mais nova do que a nossa
    copia mais nova, entao entrou la alguma coisa depois de a termos visto.
    """
    mapa: dict[str, Path] = {}
    for manifesto in RAIZ_DADOS.rglob("_origens.json"):
        try:
            dados = json.loads(manifesto.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for nome, registo in dados.items():
            url = registo if isinstance(registo, str) else registo.get("url", "")
            if not url:
                continue
            alvo = manifesto.parent / nome
            if not alvo.exists():
                continue
            chave = _pedivel(url)
            actual = mapa.get(chave)
            if actual is None or alvo.stat().st_mtime > actual.stat().st_mtime:
                mapa[chave] = alvo
    return mapa


def paginas_por_ficheiro() -> dict[str, dict]:
    """Cada ficheiro remoto do indice, com quantas paginas tem e se leva ancora."""
    conexao = storage.abrir(CAMINHO_BANCO)
    try:
        linhas = conexao.execute("SELECT origem, titulo FROM documents").fetchall()
    finally:
        conexao.close()

    juntos: dict[str, dict] = defaultdict(
        lambda: {"paginas": 0, "ancorado": False, "exemplo": ""}
    )
    for origem, titulo in linhas:
        if not origem.startswith(("http://", "https://")):
            continue
        alvo = juntos[_ficheiro_de(origem)]
        alvo["paginas"] += 1
        alvo["ancorado"] = alvo["ancorado"] or "#pagina=" in origem
        alvo["exemplo"] = alvo["exemplo"] or titulo
    return dict(juntos)


def _quando(resposta) -> datetime | None:
    bruto = resposta.headers.get("Last-Modified")
    if not bruto:
        return None
    try:
        return parsedate_to_datetime(bruto)
    except (TypeError, ValueError):
        return None


def examinar(sessao, url: str, local: Path | None) -> tuple[str, str]:
    """(veredicto, porque)."""
    try:
        resposta = sessao.head(url, timeout=TEMPO_LIMITE, allow_redirects=True)
    except Exception as erro:
        return SEM_RESPOSTA, f"{type(erro).__name__}"

    if resposta.status_code == 405:
        # Nem todos os servidores respondem a HEAD. Pede-se um byte so.
        try:
            resposta = sessao.get(
                url, timeout=TEMPO_LIMITE, headers={"Range": "bytes=0-0"}
            )
        except Exception as erro:
            return SEM_RESPOSTA, f"{type(erro).__name__}"
    if resposta.status_code in (401, 403):
        return SEM_RESPOSTA, f"estado {resposta.status_code} (sessao?)"
    if resposta.status_code >= 400:
        return SUMIU, f"estado {resposta.status_code}"

    if local is None or not local.exists():
        return SEM_RESPOSTA, "sem copia local para comparar"

    estado = local.stat()
    nossa = datetime.fromtimestamp(estado.st_mtime, tz=timezone.utc)

    publicado = _quando(resposta)
    if publicado and publicado > nossa:
        dias = (publicado - nossa).days
        return MUDOU, f"publicado {dias} dia(s) depois da nossa copia"

    tamanho = resposta.headers.get("Content-Length")
    if tamanho and tamanho.isdigit() and resposta.status_code == 200:
        if int(tamanho) != estado.st_size:
            return MUDOU, f"{int(tamanho)} bytes contra {estado.st_size} cá"

    if not publicado and not tamanho:
        return NAO_VERIFICAVEL, "gerado na hora; sem data nem tamanho para comparar"
    return FRESCO, ""


def main() -> int:
    # A consola do Windows e cp1252 e alguns nomes de ficheiro do Moodle trazem
    # acentos (ou mojibake de acentos). Sem isto o relatorio rebentava depois de
    # todos os pedidos ja terem sido feitos, que e a pior altura possivel.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--intervalo", type=float, default=1.0)
    analisador.add_argument(
        "--so-ancoradas", action="store_true",
        help="so os ficheiros com #pagina=, que sao os que derivam",
    )
    opcoes = analisador.parse_args()

    if not CAMINHO_BANCO.exists():
        print("Indice nao encontrado.")
        return 1

    ficheiros = paginas_por_ficheiro()
    if opcoes.so_ancoradas:
        ficheiros = {u: d for u, d in ficheiros.items() if d["ancorado"]}
    locais = mapa_local()

    sessao = requests.Session()
    sessao.headers["User-Agent"] = moodle.AGENTE
    try:
        url_base, utilizador, senha = moodle.configuracao()
        sessao = moodle.iniciar_sessao(url_base, utilizador, senha)
        sessao.headers["User-Agent"] = moodle.AGENTE
        print("sessao do Moodle iniciada")
    except Exception as erro:
        print(f"sem sessao do Moodle ({erro}); os ficheiros de la vao dar 403")

    print(f"{len(ficheiros)} ficheiros a verificar, {opcoes.intervalo}s entre pedidos")
    print()

    # Varios ficheiros do indice partilham o mesmo endereco pedivel - todos os
    # PDF de uma pasta do Moodle apontam para a pasta. Pergunta-se uma vez por
    # endereco e distribui-se a resposta: sao 236 pedidos em vez de 392, e o
    # servidor da escola nao leva a mesma pergunta sete vezes seguidas.
    vistos: dict[str, tuple[str, str]] = {}
    resultados = []
    ultimo = 0.0
    for numero, (url, dados) in enumerate(
        sorted(ficheiros.items(), key=lambda p: -p[1]["paginas"]), start=1
    ):
        pedivel = _pedivel(url)
        if pedivel in vistos:
            veredicto, porque = vistos[pedivel]
        else:
            espera = opcoes.intervalo - (time.monotonic() - ultimo)
            if espera > 0:
                time.sleep(espera)
            ultimo = time.monotonic()
            veredicto, porque = examinar(sessao, pedivel, locais.get(pedivel))
            vistos[pedivel] = (veredicto, porque)
        resultados.append((veredicto, porque, url, dados))
        marca = {MUDOU: "!", SUMIU: "x", FRESCO: ".",
                 SEM_RESPOSTA: "?", NAO_VERIFICAVEL: "-"}[veredicto]
        print(marca, end="", flush=True)
        if numero % 60 == 0:
            print()

    print()
    print()
    ordem = {MUDOU: 0, SUMIU: 1, SEM_RESPOSTA: 2, NAO_VERIFICAVEL: 3, FRESCO: 4}
    graves = [r for r in resultados if r[0] == MUDOU and r[3]["ancorado"]]
    # Por endereco e nao por igualdade do tuplo: os tuplos levam dicionarios
    # dentro, e `in` numa lista compara-os por valor. Dois ficheiros diferentes
    # com o mesmo numero de paginas podiam anular-se um ao outro.
    enderecos_graves = {r[2] for r in graves}
    if graves:
        print("=" * 72)
        print("GRAVE - mudou na origem E o indice guarda numeros de pagina.")
        print("        O aluno abre a pagina certa de um ficheiro que ja e outro.")
        print("=" * 72)
        for _, porque, url, dados in sorted(graves, key=lambda r: -r[3]["paginas"]):
            print(f"  {dados['paginas']:>4} paginas  {url}")
            print(f"              {porque}")
        print()

    for estado in (MUDOU, SUMIU, SEM_RESPOSTA):
        do_estado = [
            r for r in resultados
            if r[0] == estado and r[2] not in enderecos_graves
        ]
        if not do_estado:
            continue
        print(f"--- {estado} ({len(do_estado)}) ---")
        for _, porque, url, dados in sorted(do_estado, key=lambda r: -r[3]["paginas"]):
            ancora = " [com paginas]" if dados["ancorado"] else ""
            print(f"  {dados['paginas']:>4}p{ancora:<14} {url[:82]}")
            if porque:
                print(f"        {porque}")
        print()

    contagem = {e: sum(1 for r in resultados if r[0] == e) for e in ordem}
    print(
        f"frescos {contagem[FRESCO]} | mudaram {contagem[MUDOU]} | "
        f"sumiram {contagem[SUMIU]} | sem resposta {contagem[SEM_RESPOSTA]} | "
        f"nao verificaveis {contagem[NAO_VERIFICAVEL]}"
    )
    if contagem[NAO_VERIFICAVEL]:
        print(
            "  (nao verificavel = o servidor respondeu mas nao manda data"
            " nem tamanho: sao as paginas geradas na hora, e nao um defeito"
            " do indice)"
        )
    if graves:
        print()
        print("Para corrigir: python main.py atualizar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
