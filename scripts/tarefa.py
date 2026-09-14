"""Um passo de manutencao, para o Agendador de Tarefas do Windows.

    python scripts/tarefa.py conteudos --etiqueta manha
    python scripts/tarefa.py horario

Porque e que isto e Python e nao um .cmd, como era antes: um ficheiro de lote
nao se testa. A logica aqui - "verifica, e SO se houve novidade paga os dois
minutos de reindexacao" - e uma decisao com consequencias (reindexar tres
vezes por dia durante um mes sao horas de CPU gastas a olhar para um corpus
que nao mudou), e decisoes com consequencias merecem um teste.

O outro motivo e mais prosaico: chamado com `pythonw.exe`, isto corre sem
abrir janela nenhuma. Um `cmd.exe` agendado de hora a hora pisca uma consola
preta por cima do que estiver no ecra - feio na secretaria, pior com o
projetor da sala ligado.

Sem consola, `sys.stdout` e None e o primeiro `print()` de qualquer modulo
rebentava. Por isso a primeira coisa que se faz e trocar o stdout por um que
escreve no registo: e o registo a unica testemunha de uma tarefa que corre sem
ninguem a ver.
"""

import argparse
import io
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

REGISTOS = {
    "conteudos": Path("data") / "verificacao.log",
    "horario": Path("data") / "horario.log",
}

# Acima disto o registo e rodado para .log.1. Uma tarefa de hora a hora escreve
# muito pouco, mas "muito pouco" vezes sempre acaba em megabytes, e um registo
# que ninguem abre porque demora a abrir nao serve de nada.
BYTES_MAXIMOS = 512 * 1024


class Registo:
    """Escreve no ficheiro e, se houver consola, tambem nela.

    Faz de `sys.stdout`, portanto tem de aceitar tudo o que um `print` lhe
    atire sem nunca levantar excecao: se o registo rebentar, a tarefa morre sem
    deixar dito porque.
    """

    def __init__(self, caminho: Path, tambem_no_ecra=None) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if caminho.exists() and caminho.stat().st_size > BYTES_MAXIMOS:
            caminho.replace(caminho.with_name(caminho.name + ".1"))
        self._ficheiro = caminho.open("a", encoding="utf-8", errors="replace")
        self._ecra = tambem_no_ecra

    def write(self, texto: str) -> int:
        self._ficheiro.write(texto)
        if self._ecra is not None:
            try:
                self._ecra.write(texto)
            except Exception:
                self._ecra = None
        return len(texto)

    def flush(self) -> None:
        for destino in (self._ficheiro, self._ecra):
            if destino is None:
                continue
            try:
                destino.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return False

    def fechar(self) -> None:
        self.flush()
        self._ficheiro.close()


def cabecalho(etiqueta: str = "") -> str:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"\n===== {agora}{f'  [{etiqueta}]' if etiqueta else ''} ====="


def passo_conteudos(programa, encabecar) -> int:
    """Procura material novo no Moodle e reindexa so se houver.

    Devolve o codigo de saida do processo: 0 correu bem, 1 falhou.
    """
    encabecar()
    codigo = programa.comando_verificar_moodle(None, 1.0)
    if codigo == programa.SAIDA_FALHA:
        print("FALHOU a verificacao.")
        return 1
    if codigo != programa.SAIDA_NOVIDADE:
        print("Nada de novo: nao vale reindexar.")
        return 0
    print()
    print("Material novo: a reindexar...")
    programa.comando_atualizar("", 0, 1.0, sem_rastreio=True)
    print("Concluido.")
    return 0


def passo_horario(programa, encabecar) -> int:
    """Ve se saiu horario novo, e so entao reindexa.

    A saida e guardada em memoria antes de ir para o registo porque isto corre
    de hora a hora e quase sempre nao faz nada: escrever "nada a fazer" vinte e
    quatro vezes por dia enterrava as vezes em que fez algo. So se registam as
    corridas que falaram com o servidor.
    """
    memoria = io.StringIO()
    with redirect_stdout(memoria):
        codigo = programa.comando_horario()
    texto = memoria.getvalue()

    if codigo == 0 and "Nada a fazer" in texto:
        return 0

    encabecar()
    print(texto, end="")
    if codigo == programa.SAIDA_FALHA:
        print("FALHOU a verificacao do horario.")
        return 1
    if codigo == programa.SAIDA_NOVIDADE:
        print("Horario novo: a reindexar...")
        programa.comando_atualizar("", 0, 1.0, sem_rastreio=True)
        print("Concluido.")
    return 0


PASSOS = {"conteudos": passo_conteudos, "horario": passo_horario}


def correr(passo: str, etiqueta: str = "", raiz: Path = RAIZ) -> int:
    registo = Registo(raiz / REGISTOS[passo], sys.stdout)
    anterior = (sys.stdout, sys.stderr)
    sys.stdout = sys.stderr = registo
    escrito = False

    def encabecar() -> None:
        nonlocal escrito
        if not escrito:
            escrito = True
            print(cabecalho(etiqueta))

    try:
        # Importado aqui dentro, e nao no topo: `main` imprime ao ser usado, e
        # a partir deste ponto ha para onde imprimir.
        import main as programa

        return PASSOS[passo](programa, encabecar)
    except Exception:
        encabecar()
        print("REBENTOU:")
        traceback.print_exc(file=registo)
        return 1
    finally:
        registo.fechar()
        sys.stdout, sys.stderr = anterior


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Um passo de manutencao da Madalena Search."
    )
    analisador.add_argument("passo", choices=sorted(PASSOS))
    analisador.add_argument(
        "--etiqueta", default="", help="so para o registo: manha, tarde, noite"
    )
    argumentos = analisador.parse_args()
    return correr(argumentos.passo, argumentos.etiqueta)


if __name__ == "__main__":
    sys.exit(main())
