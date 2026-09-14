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

# Ao fim de quantos dias o registo de uso e apagado. O RGPD nao fixa um
# numero, fixa o principio (art. 5.o/1/e): guarda-se o tempo necessario para
# a finalidade e nem mais um dia. A finalidade aqui e afinar o motor contra
# uso real, e tres meses cobrem um periodo escolar inteiro.
DIAS_DE_RETENCAO = 90

# A consulta guardada e cortada a este comprimento. Ninguem escreve uma
# pergunta de 400 caracteres na caixa de busca - mas alguem cola la um
# texto por engano, e nesse caso o que fica registado e o texto colado.
LIMITE_CONSULTA = 120

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

-- Uma linha por participante, reescrita: "esteve aqui a esta hora, deste tipo
-- de aparelho, nesta pagina". Nao guarda historico de proposito - para saber o
-- que alguem fez ha uma semana ja existe a tabela de eventos, e duplicar isso
-- aqui era guardar duas vezes a mesma coisa sobre uma pessoa.
--
-- Repare-se no que NAO esta nas colunas: nem o endereco IP nem a cadeia
-- User-Agent. A pagina de estatisticas diz "sem nomes, sem IPs" e o aviso de
-- privacidade diz o mesmo; para desenhar um icone de telemovel basta a palavra
-- "telemovel", e o User-Agent completo e uma impressao digital do aparelho.
CREATE TABLE IF NOT EXISTS presenca (
    participante TEXT PRIMARY KEY,
    visto        TEXT NOT NULL,
    dispositivo  TEXT,
    pagina       TEXT
);
"""

# Ao fim de quantos segundos sem um pedido se considera que a pessoa saiu. Cinco
# minutos: quem esta a ler um PDF de dez paginas nao faz pedido nenhum durante
# minutos e continua la, e um limite de um minuto punha a turma toda a piscar
# entre online e offline.
SEGUNDOS_ONLINE = 300


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
    if consulta is not None:
        consulta = consulta[:LIMITE_CONSULTA]
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



# ---------------------------------------------------------------- presenca


def marcar_presenca(
    conexao: sqlite3.Connection,
    participante: str,
    dispositivo: str | None = None,
    pagina: str | None = None,
) -> None:
    """Reescreve a linha desta pessoa. Chamada a cada pedido autenticado.

    E um UPSERT numa tabela de oito linhas, portanto custa menos de um
    milissegundo - mas mesmo assim quem chama esta funcao estrangula-a no tempo
    (`presenca.py`), porque o indice vive num disco mecanico e escrever uma vez
    por pedido de cada aluno e escrever muito mais vezes do que a informacao
    muda.
    """
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _tranca, conexao:
        conexao.execute(
            "INSERT INTO presenca (participante, visto, dispositivo, pagina)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(participante) DO UPDATE SET"
            "   visto = excluded.visto,"
            # COALESCE: um pedido sem User-Agent (curl, uma sonda) nao deve
            # apagar o aparelho que ja se sabia.
            "   dispositivo = COALESCE(excluded.dispositivo, presenca.dispositivo),"
            "   pagina = COALESCE(excluded.pagina, presenca.pagina)",
            (participante, agora, dispositivo, pagina),
        )


def presencas(conexao: sqlite3.Connection) -> dict[str, dict]:
    """Tudo o que se sabe sobre quando cada pessoa esteve aqui, por rotulo."""
    cursor = conexao.execute(
        "SELECT participante, visto, dispositivo, pagina FROM presenca"
    )
    return {
        linha[0]: {"visto": linha[1], "dispositivo": linha[2], "pagina": linha[3]}
        for linha in cursor.fetchall()
    }


def ultimos_eventos(conexao: sqlite3.Connection) -> dict[str, dict]:
    """O evento mais recente de cada participante, numa consulta so.

    Uma por pessoa seriam oito idas ao disco para desenhar uma tabela; o
    `MAX(id)` agrupado resolve tudo de uma vez. O id serve de relogio porque e
    AUTOINCREMENT: o `momento` tem resolucao de segundos e dois eventos no mesmo
    segundo empatavam.
    """
    cursor = conexao.execute(
        "SELECT participante, tipo, consulta, disciplina, doc_id, momento"
        " FROM eventos WHERE id IN (SELECT MAX(id) FROM eventos GROUP BY participante)"
    )
    colunas = [c[0] for c in cursor.description]
    return {linha[0]: dict(zip(colunas, linha)) for linha in cursor.fetchall()}


def ultimo_id(conexao: sqlite3.Connection) -> int:
    """O numero do evento mais recente. Serve de relogio exacto.

    O `momento` tem resolucao de segundos, e isso chega para um grafico mas nao
    para responder a "o que aconteceu depois de eu ter olhado": um evento
    registado no mesmo segundo da marca tem o mesmo carimbo e a comparacao
    deixa-o de fora. O id e AUTOINCREMENT e nao tem esse problema.
    """
    return _um(conexao, "SELECT MAX(id) FROM eventos")


def contar_depois_de(conexao: sqlite3.Connection, tipo: str, marca: int) -> int:
    """Quantos eventos deste tipo entraram depois do evento numero `marca`."""
    return _um(
        conexao,
        "SELECT COUNT(*) FROM eventos WHERE tipo = ? AND id > ?",
        (tipo, marca),
    )


def totais_por_tipo(conexao: sqlite3.Connection) -> dict[str, int]:
    return dict(
        conexao.execute("SELECT tipo, COUNT(*) FROM eventos GROUP BY tipo").fetchall()
    )


def apagar_antigos(conexao, dias: int = DIAS_DE_RETENCAO) -> int:
    """Apaga os eventos mais velhos do que `dias`. Devolve quantos saíram.

    Corre ao arrancar o servidor. Nao ha agendador nenhum e nao e preciso: o
    servidor e reiniciado com frequencia, e mesmo que nao fosse, um dia a mais
    de retencao nao e o problema - o problema era nao haver limite nenhum, que
    era o caso ate aqui.
    """
    from datetime import timedelta

    limite = (datetime.now(timezone.utc).date() - timedelta(days=dias)).isoformat()
    with _tranca, conexao:
        cursor = conexao.execute("DELETE FROM eventos WHERE dia < ?", (limite,))
        # A presenca tambem sai: e uma linha por pessoa, mas continua a ser um
        # "esta pessoa esteve aqui" e nao tem razao para sobreviver ao prazo.
        conexao.execute("DELETE FROM presenca WHERE visto < ?", (limite,))
        return cursor.rowcount


def zerar(conexao) -> int:
    """Apaga o registo de uso inteiro. Devolve quantos eventos sairam.

    Nao e o mesmo que `apagar_antigos`: aquilo e a retencao a funcionar, isto
    e comecar um piloto com a folha limpa. As trezentas buscas que ha aqui
    antes do dia 15 sao minhas, a testar - se ficassem, cada media da semana
    de beta vinha contaminada por uso que nao e de ninguem da turma.

    O VACUUM vem depois porque o SQLite nao devolve o espaco ao disco quando
    se apaga: sem ele, o ficheiro continuaria a ter o tamanho de antes, e as
    consultas antigas continuariam legiveis nas paginas livres com um editor
    hexadecimal. Apagar tem de apagar.
    """
    with _tranca, conexao:
        quantos = conexao.execute("DELETE FROM eventos").rowcount
        conexao.execute("DELETE FROM presenca")
    with _tranca:
        conexao.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conexao.execute("VACUUM")
    return quantos


def eventos_de(conexao, participante: str) -> list[dict]:
    """Tudo o que esta registado sobre um participante (art. 15.o do RGPD)."""
    cursor = conexao.execute(
        "SELECT momento, tipo, consulta, disciplina, resultados, modo, doc_id,"
        " posicao FROM eventos WHERE participante = ? ORDER BY momento",
        (participante,),
    )
    colunas = [c[0] for c in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def esquecer(conexao, participante: str) -> int:
    """Apaga tudo o que toca a um participante (art. 17.o do RGPD)."""
    with _tranca, conexao:
        cursor = conexao.execute(
            "DELETE FROM eventos WHERE participante = ?", (participante,)
        )
        conexao.execute(
            "DELETE FROM presenca WHERE participante = ?", (participante,)
        )
        return cursor.rowcount
