import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

CAMINHO_USO = Path("data") / "uso.sqlite3"

EVENTO_BUSCA = "busca"
EVENTO_ABERTURA = "abertura"
EVENTO_PREVIEW = "preview"
EVENTO_SUGESTAO = "sugestao_aceite"
EVENTO_ENTRADA = "entrada"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    momento      TEXT NOT NULL,
    dia          TEXT NOT NULL,
    participante TEXT NOT NULL,
    tipo         TEXT NOT NULL,
    consulta     TEXT,
    disciplina   TEXT,
    resultados   INTEGER,
    modo         TEXT,
    doc_id       INTEGER,
    posicao      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos(tipo);
CREATE INDEX IF NOT EXISTS idx_eventos_dia ON eventos(dia);
"""


def abrir(
    caminho: str | Path = CAMINHO_USO, entre_fios: bool = False
) -> sqlite3.Connection:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, check_same_thread=not entre_fios)

    # WAL: os leitores deixam de bloquear quem escreve. Medido com o servidor
    # a correr, registar um evento custava 322 ms - cinquenta vezes mais que a
    # busca inteira - porque cada pedido esperava pelo bloqueio do ficheiro.
    #
    # synchronous=NORMAL: o WAL deixa de ser sincronizado com o disco a cada
    # commit, so nos checkpoints. Numa falha de energia perdem-se os ultimos
    # eventos. Isto e o registo de quantas buscas se fizeram, nao o indice nem
    # os participantes, que vivem noutros ficheiros: e uma troca boa.
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("PRAGMA synchronous=NORMAL")

    conexao.executescript(_ESQUEMA)
    return conexao


_partilhada: sqlite3.Connection | None = None
_tranca = threading.Lock()


def partilhada(caminho: str | Path = CAMINHO_USO) -> sqlite3.Connection:
    """Uma ligacao para o processo todo, nunca fechada.

    Abrir e fechar por pedido custava 190 ms cada: em WAL, fechar a ultima
    ligacao dispara um checkpoint, que reescreve o WAL no ficheiro e espera
    pelo disco. Abrir custa 2 ms e escrever 2 ms - era o fecho que pesava,
    e era feito a cada busca de cada aluno.

    Partilhar entre fios obriga a serializar as escritas com uma tranca. A
    escrita e de milissegundos, portanto oito alunos em simultaneo esperam
    dezenas de milissegundos, nao segundos.
    """
    global _partilhada
    with _tranca:
        if _partilhada is None:
            _partilhada = abrir(caminho, entre_fios=True)
        return _partilhada


def fechar_partilhada() -> None:
    """Para os testes: a proxima chamada abre de novo."""
    global _partilhada
    with _tranca:
        if _partilhada is not None:
            _partilhada.close()
            _partilhada = None


def registar(
    conexao: sqlite3.Connection,
    participante: str,
    tipo: str,
    consulta: str | None = None,
    disciplina: str | None = None,
    resultados: int | None = None,
    modo: str | None = None,
    doc_id: int | None = None,
    posicao: int | None = None,
) -> None:
    agora = datetime.now(timezone.utc)
    # A tranca so tem efeito na ligacao partilhada; noutras e um no-op barato.
    with _tranca, conexao:
        conexao.execute(
            "INSERT INTO eventos (momento, dia, participante, tipo, consulta,"
            " disciplina, resultados, modo, doc_id, posicao)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agora.isoformat(timespec="seconds"),
                agora.date().isoformat(),
                participante,
                tipo,
                consulta,
                disciplina,
                resultados,
                modo,
                doc_id,
                posicao,
            ),
        )


def _um(conexao: sqlite3.Connection, sql: str, parametros=()) -> int:
    valor = conexao.execute(sql, parametros).fetchone()[0]
    return valor or 0


def resumo(conexao: sqlite3.Connection) -> dict:
    buscas = _um(conexao, "SELECT COUNT(*) FROM eventos WHERE tipo = ?", (EVENTO_BUSCA,))
    vazias = _um(
        conexao,
        "SELECT COUNT(*) FROM eventos WHERE tipo = ? AND resultados = 0",
        (EVENTO_BUSCA,),
    )
    parciais = _um(
        conexao,
        "SELECT COUNT(*) FROM eventos WHERE tipo = ? AND modo = 'ou'",
        (EVENTO_BUSCA,),
    )
    aberturas = _um(
        conexao, "SELECT COUNT(*) FROM eventos WHERE tipo = ?", (EVENTO_ABERTURA,)
    )
    return {
        "buscas": buscas,
        "participantes": _um(conexao, "SELECT COUNT(DISTINCT participante) FROM eventos"),
        "dias": _um(conexao, "SELECT COUNT(DISTINCT dia) FROM eventos"),
        "aberturas": aberturas,
        "sugestoes_aceites": _um(
            conexao, "SELECT COUNT(*) FROM eventos WHERE tipo = ?", (EVENTO_SUGESTAO,)
        ),
        "taxa_vazias": (vazias / buscas * 100) if buscas else 0.0,
        "taxa_parciais": (parciais / buscas * 100) if buscas else 0.0,
        "taxa_abertura": (aberturas / buscas * 100) if buscas else 0.0,
    }


def por_dia(conexao: sqlite3.Connection) -> list[tuple[str, int]]:
    return conexao.execute(
        "SELECT dia, COUNT(*) FROM eventos WHERE tipo = ?"
        " GROUP BY dia ORDER BY dia",
        (EVENTO_BUSCA,),
    ).fetchall()


def por_participante(conexao: sqlite3.Connection) -> list[tuple[str, int, int]]:
    return conexao.execute(
        "SELECT participante,"
        " SUM(CASE WHEN tipo = 'busca' THEN 1 ELSE 0 END),"
        " SUM(CASE WHEN tipo = 'abertura' THEN 1 ELSE 0 END)"
        " FROM eventos GROUP BY participante ORDER BY 2 DESC",
    ).fetchall()


def consultas_populares(
    conexao: sqlite3.Connection, limite: int = 15, minimo_participantes: int = 1
):
    return conexao.execute(
        "SELECT consulta, COUNT(*), SUM(CASE WHEN resultados = 0 THEN 1 ELSE 0 END)"
        " FROM eventos WHERE tipo = ? AND consulta <> ''"
        " GROUP BY LOWER(consulta)"
        " HAVING COUNT(DISTINCT participante) >= ?"
        " ORDER BY 2 DESC LIMIT ?",
        (EVENTO_BUSCA, minimo_participantes, limite),
    ).fetchall()


def consultas_sem_resultado(
    conexao: sqlite3.Connection, limite: int = 15, minimo_participantes: int = 1
):
    """minimo_participantes=2 esconde consultas feitas por uma so pessoa.

    Com 8 participantes, uma consulta unica identifica quem a escreveu.
    """
    return conexao.execute(
        "SELECT consulta, COUNT(*) FROM eventos"
        " WHERE tipo = ? AND resultados = 0 AND consulta <> ''"
        " GROUP BY LOWER(consulta)"
        " HAVING COUNT(DISTINCT participante) >= ?"
        " ORDER BY 2 DESC LIMIT ?",
        (EVENTO_BUSCA, minimo_participantes, limite),
    ).fetchall()


def disciplinas_filtradas(conexao: sqlite3.Connection):
    return conexao.execute(
        "SELECT disciplina, COUNT(*) FROM eventos"
        " WHERE tipo = ? AND disciplina IS NOT NULL AND disciplina <> ''"
        " GROUP BY disciplina ORDER BY 2 DESC",
        (EVENTO_BUSCA,),
    ).fetchall()


def consultas_da_disciplina(
    conexao: sqlite3.Connection, disciplina: str, limite: int = 6
):
    return conexao.execute(
        "SELECT consulta, COUNT(*) FROM eventos"
        " WHERE tipo = ? AND disciplina = ? AND resultados > 0 AND consulta <> ''"
        " GROUP BY LOWER(consulta)"
        " HAVING COUNT(DISTINCT participante) >= 2"
        " ORDER BY 2 DESC LIMIT ?",
        (EVENTO_BUSCA, disciplina, limite),
    ).fetchall()


def documentos_mais_abertos(conexao: sqlite3.Connection, limite: int = 40):
    return conexao.execute(
        "SELECT doc_id, COUNT(*) FROM eventos"
        " WHERE tipo = ? AND doc_id IS NOT NULL"
        " GROUP BY doc_id ORDER BY 2 DESC LIMIT ?",
        (EVENTO_ABERTURA, limite),
    ).fetchall()

