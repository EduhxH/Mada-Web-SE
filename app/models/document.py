from dataclasses import dataclass


@dataclass(frozen=True)
class Documento:
    id: int
    titulo: str
    texto: str
    origem: str
    disciplina: str = ""

    @property
    def texto_pesquisavel(self) -> str:
        return f"{self.titulo} {self.disciplina} {self.texto}"
