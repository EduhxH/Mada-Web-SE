from dataclasses import dataclass


@dataclass(frozen=True)
class Documento:
    id: int
    titulo: str
    texto: str
    origem: str
    disciplina: str = ""
