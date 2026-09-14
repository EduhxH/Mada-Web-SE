"""O registo do servidor, para o painel poder mostrar o que esta a acontecer.

Antes disto o `log_message` do `BaseHTTPRequestHandler` era um `pass`: os
pedidos nao apareciam em sitio nenhum e um erro dentro de um pedido morria em
silencio na consola de quem tinha arrancado o servidor - que numa apresentacao
esta minimizada atras do browser. Se algo corresse mal na sala de aula, a unica
pista era "nao funciona".

Duas memorias, de proposito diferente:

**Em memoria** ficam todas as linhas, com um numero de sequencia. E daqui que
o painel le, pedindo "o que ha de novo depois do numero N" - o que torna a vista
ao vivo um pedido pequeno em vez de reenviar o registo inteiro a cada segundo.
Morre com o processo, e ser volatil e uma caracteristica: as linhas de pedido
levam consigo o que a pessoa pesquisou, e isso nao tem razao para ficar no disco
sem prazo de validade.

**No disco** (`data/servidor.log`) fica so o que e aviso ou erro. Sao as linhas
que interessam depois de um estouro, e sao as que nao contem o que ninguem
pesquisou. Se o servidor morre, e la que fica escrito porque.
"""

import threading
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path

INFO = "info"
AVISO = "aviso"
ERRO = "erro"

NIVEIS = (INFO, AVISO, ERRO)
GRAVES = (AVISO, ERRO)

# Linhas guardadas em memoria. Mil linhas sao uns 150 KB e cobrem largamente
# uma aula inteira de oito pessoas a pesquisar.
MAXIMO_LINHAS = 1000

CAMINHO_DISCO = Path("data") / "servidor.log"
BYTES_MAXIMOS_DISCO = 1024 * 1024

# Um texto maior do que isto numa linha de registo e um acidente (uma resposta
# inteira, um traceback colado). Corta-se para o painel continuar legivel.
LIMITE_TEXTO = 2000


class _Registo:
    def __init__(self) -> None:
        self._linhas: deque[dict] = deque(maxlen=MAXIMO_LINHAS)
        self._seguinte = 1
        self._tranca = threading.Lock()
        self._disco_avisado = False

    def anotar(self, nivel: str, texto: str, origem: str = "servidor") -> dict:
        if nivel not in NIVEIS:
            nivel = INFO
        linha = {
            "seq": 0,
            "momento": datetime.now().isoformat(timespec="seconds"),
            "nivel": nivel,
            "origem": origem[:24],
            "texto": str(texto)[:LIMITE_TEXTO],
        }
        with self._tranca:
            linha["seq"] = self._seguinte
            self._seguinte += 1
            self._linhas.append(linha)
        if nivel in GRAVES:
            self._para_o_disco(linha)
        return linha

    def excecao(self, contexto: str, origem: str = "servidor") -> dict:
        """Anota o estouro que esta a ser tratado, com a pilha inteira."""
        return self.anotar(ERRO, f"{contexto}\n{traceback.format_exc()}", origem)

    def desde(self, seq: int = 0, limite: int = MAXIMO_LINHAS) -> tuple[list[dict], int]:
        """As linhas com numero maior do que `seq`, e o numero da ultima.

        Devolver o ultimo numero mesmo quando nao ha linhas novas e o que deixa
        o painel pedir sempre a partir do sitio certo - senao, ao rodar o
        buffer, voltava a receber tudo.
        """
        with self._tranca:
            todas = list(self._linhas)
            ultimo = self._seguinte - 1
        novas = [linha for linha in todas if linha["seq"] > seq]
        return novas[-limite:], ultimo

    def ultimo_seq(self) -> int:
        with self._tranca:
            return self._seguinte - 1

    def contar_desde(self, seq: int, niveis: tuple[str, ...] = GRAVES) -> int:
        with self._tranca:
            return sum(
                1
                for linha in self._linhas
                if linha["seq"] > seq and linha["nivel"] in niveis
            )

    def limpar(self) -> None:
        """Esvazia a memoria sem mexer no numero de sequencia.

        Continuar a contar e importante: o painel guarda "ja vi ate ao N", e se
        a numeracao voltasse a um, tudo o que viesse depois parecia ja visto.
        """
        with self._tranca:
            self._linhas.clear()

    def _para_o_disco(self, linha: dict) -> None:
        try:
            CAMINHO_DISCO.parent.mkdir(parents=True, exist_ok=True)
            if (
                CAMINHO_DISCO.exists()
                and CAMINHO_DISCO.stat().st_size > BYTES_MAXIMOS_DISCO
            ):
                CAMINHO_DISCO.replace(
                    CAMINHO_DISCO.with_name(CAMINHO_DISCO.name + ".1")
                )
            with CAMINHO_DISCO.open("a", encoding="utf-8", errors="replace") as f:
                f.write(
                    f"{linha['momento']}  {linha['nivel'].upper():5s} "
                    f"[{linha['origem']}] {linha['texto']}\n"
                )
        except OSError:
            # O disco cheio ou sem permissoes nao pode derrubar o servidor por
            # causa de uma linha de registo. Avisa-se uma vez, em memoria, e
            # segue-se - a vista ao vivo do painel continua a funcionar.
            if not self._disco_avisado:
                self._disco_avisado = True
                self.anotar(AVISO, f"nao consigo escrever em {CAMINHO_DISCO}")


_registo = _Registo()

anotar = _registo.anotar
excecao = _registo.excecao
desde = _registo.desde
ultimo_seq = _registo.ultimo_seq
contar_desde = _registo.contar_desde
limpar = _registo.limpar


class Canal:
    """Um objeto que se passa a `sys.stdout` e vai dar ao registo.

    As operacoes manuais do painel chamam codigo escrito para a linha de
    comandos, que comunica com `print`. Em vez de reescrever esse codigo para
    devolver texto, encaminha-se o `print`: cada linha completa vira uma entrada
    de registo, e o painel mostra a operacao a correr ao vivo.
    """

    def __init__(self, origem: str, nivel: str = INFO) -> None:
        self.origem = origem
        self.nivel = nivel
        self._pendente = ""

    def write(self, texto: str) -> int:
        self._pendente += texto
        while "\n" in self._pendente:
            linha, self._pendente = self._pendente.split("\n", 1)
            if linha.strip():
                anotar(self.nivel, linha.rstrip(), self.origem)
        return len(texto)

    def flush(self) -> None:
        if self._pendente.strip():
            anotar(self.nivel, self._pendente.rstrip(), self.origem)
        self._pendente = ""

    def isatty(self) -> bool:
        return False
