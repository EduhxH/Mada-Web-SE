import sqlite3
from pathlib import Path

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
"""


def abrir(caminho: str | Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
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
