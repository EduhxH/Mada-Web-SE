"""Mantem o projeto acessivel de fora: servidor, tunel, e a maquina acordada.

Isto existe para os dias de beta, em que o computador fica ligado e ninguem
esta a olhar para ele. Tres coisas podem falhar sozinhas nessas horas, e cada
uma delas deixa a turma de fora sem aviso:

**A maquina adormece.** O plano de energia desta maquina suspende ao fim de 15
minutos sem uso - e um portatil que fica a servir um site nao tem uso nenhum do
ponto de vista do Windows. Em vez de mexer no plano de energia, que e uma
definicao do sistema que ficaria mudada para sempre, pede-se ao Windows que nao
suspenda **enquanto este processo viver** (`ES_SYSTEM_REQUIRED`). Fechar isto
devolve a maquina ao comportamento normal, sem ter de desfazer nada. O ecra pode
apagar-se a vontade: `ES_DISPLAY_REQUIRED` fica de fora de proposito, porque
deixar um ecra aceso a noite inteira nao serve para nada.

**O servidor morre.** Por um estouro, por um fecho acidental da consola. Se
parar de responder, e levantado outra vez.

**O tunel cai.** Um tunel da Cloudflare sem conta nao tem garantias nenhumas, e
recebe um nome aleatorio novo a cada arranque. Quando cai, levanta-se outro e
publica-se o endereco novo na pagina do GitHub Pages - que e o endereco que a
turma tem nos favoritos e que nunca muda. Quem esta a meio de uma pesquisa tem de
recarregar; quem chegar depois nao da por nada.

Uso:
    python scripts/no_ar.py                 # fica a vigiar, Ctrl+C encerra
    python scripts/no_ar.py --porta 8081
    python scripts/no_ar.py --sem-tunel     # so o servidor, sem expor nada

Com `pythonw.exe` corre sem janela, e e assim que a tarefa agendada o chama.
"""

import argparse
import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

REGISTO = Path("data") / "no-ar.log"
SAIDA_SERVIDOR = Path("data") / "servidor-saida.log"
SAIDA_TUNEL = Path("data") / "tunel-saida.log"
ESTADO = Path("data") / "tunel-estado.json"

# De quanto em quanto tempo se verifica que tudo continua de pe.
INTERVALO = 20
# O tunel so e verificado de fora de vez em quando: cada verificacao e um pedido
# que sai da maquina, e de 20 em 20 segundos seriam mais de quatro mil por dia
# para confirmar o que quase nunca muda.
INTERVALO_TUNEL = 300
# Quanto se espera pelo endereco do tunel depois de o levantar.
ESPERA_ENDERECO = 90
# Falhas seguidas antes de dar o tunel por morto. Uma so pode ser a rede da
# escola a hesitar, e derrubar o tunel por causa disso trocava o endereco - e o
# endereco novo tem de ser publicado, o que demora mais do que a hesitacao.
#
# Depois de UMA falha, porem, volta-se a tentar ao ritmo normal (20s) e nao ao
# fim de cinco minutos: tres falhas espacadas de cinco minutos seriam quinze
# minutos de turma a olhar para um erro. Assim uma hesitacao custa vinte
# segundos de paciencia e um tunel mesmo morto e reposto em cerca de um minuto.
FALHAS_PARA_DESISTIR = 3

PADRAO_ENDERECO = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

# Porta que so serve de ferrolho: quem a consegue tomar e o vigia desta maquina.
# Um ficheiro com o PID nao chegava - um vigia morto a mal deixa o ficheiro para
# tras e o seguinte tinha de adivinhar se o processo ainda existe. A porta e
# devolvida pelo sistema no instante em que o processo acaba, seja como for que
# acabe. Faz falta porque a tarefa agendada repete-se de cinco em cinco minutos
# para vigiar o vigia, e sem isto cada repeticao levantaria mais um.
PORTA_FERROLHO = 8079

_BYTES_MAXIMOS = 512 * 1024


def anotar(texto: str) -> None:
    """Uma linha no registo, e na consola se houver uma."""
    linha = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {texto}"
    try:
        REGISTO.parent.mkdir(parents=True, exist_ok=True)
        if REGISTO.exists() and REGISTO.stat().st_size > _BYTES_MAXIMOS:
            REGISTO.replace(REGISTO.with_name(REGISTO.name + ".1"))
        with REGISTO.open("a", encoding="utf-8", errors="replace") as f:
            f.write(linha + "\n")
    except OSError:
        pass
    try:
        if sys.stdout is not None:
            print(linha, flush=True)
    except Exception:
        pass


# ------------------------------------------------------------ nao adormecer


def tomar_ferrolho():
    """Devolve a tomada se este for o unico vigia, ou None se ja ha outro."""
    tomada = socket.socket()
    try:
        # Sem SO_REUSEADDR de proposito: aqui queremos mesmo colidir.
        tomada.bind(("127.0.0.1", PORTA_FERROLHO))
        tomada.listen(1)
        return tomada
    except OSError:
        tomada.close()
        return None


def manter_acordado() -> bool:
    """Pede ao Windows para nao suspender enquanto este processo viver.

    Sem `ES_DISPLAY_REQUIRED`: o ecra pode apagar-se, o que se quer e que a
    maquina continue a responder. Vale so nesta sessao - nao ha definicao
    nenhuma para repor depois.
    """
    if os.name != "nt":
        return False
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        return True
    except Exception as erro:
        anotar(f"AVISO nao consegui impedir a suspensao: {erro}")
        return False


def largar_acordado() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


# ------------------------------------------------------------------ servidor


def porta_aberta(porta: int) -> bool:
    with socket.socket() as tomada:
        tomada.settimeout(2)
        return tomada.connect_ex(("127.0.0.1", porta)) == 0


def _abrir_registo(caminho: Path):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho.open("a", encoding="utf-8", errors="replace")


def arrancar_servidor(porta: int):
    """Levanta o servidor em 127.0.0.1. Devolve o processo.

    Fica no endereco local e nao em 0.0.0.0 de proposito: quem chega vem pelo
    tunel, que fala com a maquina por dentro. Abrir a porta a rede toda seria
    superficie a mais para nao ganhar nada.
    """
    interprete = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    if not interprete.exists():
        interprete = Path(sys.executable)
    return subprocess.Popen(
        [str(interprete), "main.py", "web", "--porta", str(porta)],
        cwd=RAIZ,
        stdout=_abrir_registo(SAIDA_SERVIDOR),
        stderr=subprocess.STDOUT,
    )


def esperar_porta(porta: int, segundos: int = 30) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if porta_aberta(porta):
            return True
        time.sleep(1)
    return False


# --------------------------------------------------------------------- tunel


def ler_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def guardar_estado(endereco: str) -> None:
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(
            json.dumps(
                {
                    "endereco": endereco,
                    "desde": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def arrancar_tunel(porta: int):
    from scripts.publicar_tunel import encontrar_cloudflared

    executavel = encontrar_cloudflared()
    SAIDA_TUNEL.parent.mkdir(parents=True, exist_ok=True)
    # Trunca-se: o endereco procura-se neste ficheiro, e um ficheiro com os
    # enderecos de ontem daria o de ontem.
    SAIDA_TUNEL.write_text("", encoding="utf-8")
    return subprocess.Popen(
        [executavel, "tunnel", "--url", f"http://localhost:{porta}"],
        cwd=RAIZ,
        stdout=SAIDA_TUNEL.open("a", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )


def esperar_endereco(processo, segundos: int = ESPERA_ENDERECO) -> str:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if processo.poll() is not None:
            return ""
        try:
            texto = SAIDA_TUNEL.read_text(encoding="utf-8", errors="replace")
        except OSError:
            texto = ""
        achado = PADRAO_ENDERECO.search(texto)
        if achado:
            return achado.group(0)
        time.sleep(1)
    return ""


def tunel_responde(endereco: str) -> bool:
    """Bate a porta do tunel de fora. Um 403 conta: a casa esta de pe.

    O que se quer saber e se o pedido chega ao servidor, e a pagina de entrada
    responde 200 - mas qualquer resposta HTTP prova o caminho inteiro. So a
    ausencia de resposta e que e falha.
    """
    pedido = urllib.request.Request(endereco + "/robots.txt", method="GET")
    pedido.add_header("User-Agent", "MadalenaVigia/1.0")
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return resposta.status < 500
    except urllib.error.HTTPError as erro:
        return erro.code < 500
    except Exception:
        return False


def publicar_endereco(endereco: str) -> None:
    from scripts import publicar_tunel

    try:
        publicar_tunel.publicar(endereco)
        anotar(f"pagina publica a apontar para {endereco}")
    except Exception as erro:
        # Nao poder publicar nao derruba nada: o tunel esta de pe e o endereco
        # fica no registo. O que se perde e o link estavel ficar desatualizado.
        anotar(f"AVISO nao consegui publicar a pagina: {erro}")


# ----------------------------------------------------------------- o vigia


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Mantem o servidor e o tunel de pe."
    )
    analisador.add_argument("--porta", type=int, default=8080)
    analisador.add_argument(
        "--sem-tunel", action="store_true", help="so o servidor, sem expor nada"
    )
    analisador.add_argument(
        "--uma-vez", action="store_true",
        help="verifica, corrige e sai; nao segura a maquina acordada",
    )
    opcoes = analisador.parse_args()

    os.chdir(RAIZ)
    ferrolho = tomar_ferrolho()
    if ferrolho is None:
        # Silencioso: isto acontece de cinco em cinco minutos, de propósito, e
        # anotar cada vez enchia o registo com a unica coisa que nao e noticia.
        return 0

    anotar("--- vigia a comecar ---")
    if manter_acordado():
        anotar("a maquina nao vai suspender enquanto isto correr")

    servidor = None
    tunel = None
    endereco = ler_estado().get("endereco", "")
    falhas = 0
    proxima_prova = 0.0

    try:
        while True:
            # ---------------------------------------------------- servidor
            if not porta_aberta(opcoes.porta):
                anotar(f"servidor em baixo; a levantar na porta {opcoes.porta}")
                servidor = arrancar_servidor(opcoes.porta)
                if esperar_porta(opcoes.porta):
                    anotar("servidor no ar")
                else:
                    anotar("ERRO o servidor nao respondeu a tempo")

            # ------------------------------------------------------- tunel
            if not opcoes.sem_tunel:
                morreu = tunel is not None and tunel.poll() is not None
                agora = time.monotonic()
                if endereco and not morreu and agora >= proxima_prova:
                    if tunel_responde(endereco):
                        falhas = 0
                        proxima_prova = agora + INTERVALO_TUNEL
                    else:
                        falhas += 1
                        proxima_prova = agora + INTERVALO
                        anotar(
                            f"o tunel nao respondeu ({falhas}/{FALHAS_PARA_DESISTIR})"
                        )
                if not endereco or morreu or falhas >= FALHAS_PARA_DESISTIR:
                    if tunel is not None and tunel.poll() is None:
                        tunel.terminate()
                    anotar("a levantar o tunel")
                    tunel = arrancar_tunel(opcoes.porta)
                    novo = esperar_endereco(tunel)
                    if novo:
                        endereco = novo
                        falhas = 0
                        proxima_prova = time.monotonic() + INTERVALO_TUNEL
                        anotar(f"tunel aberto em {endereco}")
                        guardar_estado(endereco)
                        publicar_endereco(endereco)
                    else:
                        anotar("ERRO o tunel nao deu endereco")
                        endereco = ""

            if opcoes.uma_vez:
                return 0
            time.sleep(INTERVALO)
    except KeyboardInterrupt:
        anotar("a encerrar a pedido")
        return 0
    finally:
        largar_acordado()
        if tunel is not None and tunel.poll() is None:
            tunel.terminate()
        ferrolho.close()
        anotar("--- vigia terminou ---")


if __name__ == "__main__":
    sys.exit(main())
