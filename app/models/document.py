from dataclasses import dataclass


@dataclass(frozen=True)
class Documento:
    id: int
    titulo: str
    texto: str
    origem: str
    disciplina: str = ""
    # Data de publicacao no formato ISO, vinda do Last-Modified da fonte.
    # Vazia quando a fonte nao a da - e o caso das pastas do Moodle, que
    # sao geradas na hora e nao tem data propria.
    data: str = ""
    # Nome da pasta do Moodle onde o documento vive: "Guioes e Fichas de
    # Trabalho", "Sebenta e Material de Apoio".
    #
    # NAO entra em texto_pesquisavel, e a tentacao e grande. Medido contra
    # avaliacao/consultas.json: indexa-lo baixa o top-1 de 17/22 para 16/22
    # e o MRR de 0.8114 para 0.7887. O nome de uma pasta injeta os seus
    # termos em todos os ficheiros dela de uma vez - "Guioes e Fichas de
    # Trabalho" poe "ficha" e "trabalho" em vinte documentos - e essas sao
    # palavras que os alunos escrevem muito. Alarga em vez de afinar.
    #
    # Fica guardado para a interface o poder mostrar e para um ranker por
    # campos, com peso proprio, o poder usar sem ser tudo ou nada.
    contexto: str = ""

    @property
    def texto_pesquisavel(self) -> str:
        return f"{self.titulo} {self.disciplina} {self.texto}"
