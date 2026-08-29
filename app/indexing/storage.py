import sqlite3
from pathlib import Path

from app.indexing.tokenizer import remover_acentos
from app.models.classificacao import EXTENSOES_CODIGO, PADROES_ADMINISTRATIVOS
from app.models.document import Documento

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id         INTEGER PRIMARY KEY,
    titulo     TEXT NOT NULL,
    origem     TEXT NOT NULL,
    texto      TEXT NOT NULL,
    tamanho    INTEGER NOT NULL,
    disciplina TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS terms (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    termo TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS postings (
    term_id INTEGER NOT NULL REFERENCES terms(id),
    doc_id  INTEGER NOT NULL REFERENCES documents(id),
    freq    INTEGER NOT NULL,
    PRIMARY KEY (term_id, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_postings_doc ON postings(doc_id);
CREATE INDEX IF NOT EXISTS idx_documents_disciplina ON documents(disciplina);
"""


def abrir(caminho: str | Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.create_function(
        "sem_acento", 1, lambda s: remover_acentos(s.lower()) if s else ""
    )
    conexao.executescript(_ESQUEMA)
    _migrar(conexao)
    return conexao


def _migrar(conexao: sqlite3.Connection) -> None:
    colunas = {
        linha[1] for linha in conexao.execute("PRAGMA table_info(documents)")
    }
    if "disciplina" not in colunas:
        with conexao:
            conexao.execute(
                "ALTER TABLE documents ADD COLUMN disciplina TEXT NOT NULL DEFAULT ''"
            )


def salvar_indice(
    conexao: sqlite3.Connection,
    documentos: list[Documento],
    indice: dict[str, dict[int, int]],
    tamanhos: dict[int, int],
) -> None:
    with conexao:
        conexao.execute("DELETE FROM postings")
        conexao.execute("DELETE FROM terms")
        conexao.execute("DELETE FROM documents")
        conexao.executemany(
            "INSERT INTO documents (id, titulo, origem, texto, tamanho, disciplina)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (d.id, d.titulo, d.origem, d.texto, tamanhos[d.id], d.disciplina)
                for d in documentos
            ],
        )
        for termo, postings in indice.items():
            cursor = conexao.execute(
                "INSERT INTO terms (termo) VALUES (?)", (termo,)
            )
            conexao.executemany(
                "INSERT INTO postings (term_id, doc_id, freq) VALUES (?, ?, ?)",
                [
                    (cursor.lastrowid, doc_id, freq)
                    for doc_id, freq in postings.items()
                ],
            )


def carregar_postings(conexao: sqlite3.Connection, termo: str) -> dict[int, int]:
    linhas = conexao.execute(
        "SELECT p.doc_id, p.freq FROM postings p"
        " JOIN terms t ON t.id = p.term_id WHERE t.termo = ?",
        (termo,),
    ).fetchall()
    return dict(linhas)


def carregar_tamanhos(conexao: sqlite3.Connection) -> dict[int, int]:
    linhas = conexao.execute("SELECT id, tamanho FROM documents").fetchall()
    return dict(linhas)


def contar_documentos(conexao: sqlite3.Connection) -> int:
    return conexao.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def carregar_documento(conexao: sqlite3.Connection, doc_id: int) -> Documento:
    linha = conexao.execute(
        "SELECT id, titulo, texto, origem, disciplina FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if linha is None:
        raise KeyError(f"Documento {doc_id} não existe no índice")
    return Documento(
        id=linha[0],
        titulo=linha[1],
        texto=linha[2],
        origem=linha[3],
        disciplina=linha[4],
    )


LOTE_MAXIMO = 500


def carregar_documentos(
    conexao: sqlite3.Connection, doc_ids: list[int]
) -> dict[int, Documento]:
    encontrados: dict[int, Documento] = {}
    for inicio in range(0, len(doc_ids), LOTE_MAXIMO):
        lote = doc_ids[inicio : inicio + LOTE_MAXIMO]
        marcadores = ",".join("?" * len(lote))
        linhas = conexao.execute(
            "SELECT id, titulo, texto, origem, disciplina FROM documents"
            f" WHERE id IN ({marcadores})",
            lote,
        ).fetchall()
        for linha in linhas:
            encontrados[linha[0]] = Documento(
                id=linha[0],
                titulo=linha[1],
                texto=linha[2],
                origem=linha[3],
                disciplina=linha[4],
            )
    return encontrados


def carregar_ids_por_disciplina(
    conexao: sqlite3.Connection, disciplina: str
) -> set[int]:
    linhas = conexao.execute(
        "SELECT id FROM documents WHERE disciplina = ?", (disciplina,)
    ).fetchall()
    return {linha[0] for linha in linhas}


def listar_disciplinas(conexao: sqlite3.Connection) -> list[str]:
    linhas = conexao.execute(
        "SELECT DISTINCT disciplina FROM documents"
        " WHERE disciplina <> '' ORDER BY disciplina"
    ).fetchall()
    return [linha[0] for linha in linhas]


def listar_vocabulario(conexao: sqlite3.Connection) -> list[tuple[str, int]]:
    return conexao.execute(
        "SELECT t.termo, COUNT(p.doc_id) FROM terms t"
        " JOIN postings p ON p.term_id = t.id GROUP BY t.id"
    ).fetchall()


def carregar_origem(conexao: sqlite3.Connection, doc_id: int) -> str | None:
    linha = conexao.execute(
        "SELECT origem FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    return linha[0] if linha else None


def _filtro_administrativo(padroes, extensoes=()) -> str:
    partes = [
        f"AND sem_acento(titulo) NOT LIKE '%{padrao}%'" for padrao in padroes
    ]
    partes += [
        f"AND sem_acento(origem) NOT LIKE '%{ext}%'" for ext in extensoes
    ]
    return " ".join(partes)


def contar_por_disciplina(
    conexao: sqlite3.Connection, disciplina: str, apenas_conteudo: bool = False
) -> int:
    extra = (
        _filtro_administrativo(PADROES_ADMINISTRATIVOS, EXTENSOES_CODIGO)
        if apenas_conteudo
        else ""
    )
    return conexao.execute(
        f"SELECT COUNT(*) FROM documents WHERE disciplina = ? {extra}",
        (disciplina,),
    ).fetchone()[0]


def df_na_disciplina(
    conexao: sqlite3.Connection,
    disciplina: str,
    minimo: int = 2,
    excluir_administrativos: bool = False,
) -> list[tuple[str, int, int]]:
    extra = ""
    if excluir_administrativos:
        extra = _filtro_administrativo(
            PADROES_ADMINISTRATIVOS, EXTENSOES_CODIGO
        )
    na_disciplina = conexao.execute(
        "SELECT p.term_id, COUNT(*) FROM postings p"
        " JOIN documents d ON d.id = p.doc_id"
        f" WHERE d.disciplina = ? {extra}"
        " GROUP BY p.term_id HAVING COUNT(*) >= ?",
        (disciplina, minimo),
    ).fetchall()
    if not na_disciplina:
        return []

    globais = dict(
        conexao.execute("SELECT term_id, COUNT(*) FROM postings GROUP BY term_id")
    )
    nomes = dict(conexao.execute("SELECT id, termo FROM terms"))
    return [
        (nomes[term_id], df_disc, globais.get(term_id, df_disc))
        for term_id, df_disc in na_disciplina
        if term_id in nomes
    ]


def documentos_da_disciplina(
    conexao: sqlite3.Connection, disciplina: str, limite: int = 10
) -> list[tuple[int, str]]:
    return conexao.execute(
        "SELECT id, titulo FROM documents WHERE disciplina = ?"
        " ORDER BY tamanho DESC LIMIT ?",
        (disciplina, limite),
    ).fetchall()


def disciplinas_dos_documentos(
    conexao: sqlite3.Connection, doc_ids: list[int]
) -> dict[int, tuple[str, str]]:
    if not doc_ids:
        return {}
    marcadores = ",".join("?" * len(doc_ids))
    linhas = conexao.execute(
        f"SELECT id, disciplina, titulo FROM documents WHERE id IN ({marcadores})",
        doc_ids,
    ).fetchall()
    return {linha[0]: (linha[1], linha[2]) for linha in linhas}


def disciplinas_por_termo(conexao: sqlite3.Connection) -> dict[str, int]:
    linhas = conexao.execute(
        "SELECT t.termo, COUNT(DISTINCT d.disciplina)"
        " FROM postings p"
        " JOIN terms t ON t.id = p.term_id"
        " JOIN documents d ON d.id = p.doc_id"
        " GROUP BY p.term_id"
    ).fetchall()
    return dict(linhas)


def contar_disciplinas(conexao: sqlite3.Connection) -> int:
    return conexao.execute(
        "SELECT COUNT(DISTINCT disciplina) FROM documents WHERE disciplina <> ''"
    ).fetchone()[0]

