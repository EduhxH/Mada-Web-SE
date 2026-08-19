import pytest

from app.models.document import Documento


@pytest.fixture
def documentos() -> list[Documento]:
    return [
        Documento(1, "Doc 1", "Python é uma linguagem de programação", "fixture"),
        Documento(2, "Doc 2", "SQLite é um banco de dados leve", "fixture"),
        Documento(3, "Doc 3", "Programação em Python usa bibliotecas", "fixture"),
        Documento(4, "Doc 4", "Python Python Python: texto repetitivo sobre Python", "fixture"),
    ]
