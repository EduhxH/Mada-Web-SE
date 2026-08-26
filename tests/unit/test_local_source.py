import io
import zipfile

from app.crawler.local_source import (
    MOTIVO_BUILD,
    MOTIVO_FORMATO,
    MOTIVO_PRIVADO,
    carregar,
)


def _criar(pasta, nome, conteudo=b"conteudo de teste com palavras"):
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    caminho.write_bytes(conteudo)
    return caminho


def test_disciplina_vem_da_pasta(tmp_path):
    _criar(tmp_path / "Matematica", "ficha.txt")
    documentos, _ = carregar(tmp_path)
    assert documentos[0].disciplina == "Matematica"


def test_pautas_sao_excluidas(tmp_path):
    _criar(tmp_path / "Fisica", "Notas Teste.txt")
    _criar(tmp_path / "Fisica", "materia.txt")
    documentos, relatorio = carregar(tmp_path)
    assert [d.titulo for d in documentos] == ["materia"]
    assert len(relatorio.por_motivo(MOTIVO_PRIVADO)) == 1


def test_criterios_de_avaliacao_nao_sao_confundidos_com_pauta(tmp_path):
    _criar(tmp_path / "Ingles", "Criterios de avaliacao da disciplina.txt")
    documentos, _ = carregar(tmp_path)
    assert len(documentos) == 1


def test_formato_nao_suportado_e_reportado(tmp_path):
    _criar(tmp_path / "TIC", "planilha.xlsx")
    documentos, relatorio = carregar(tmp_path)
    assert documentos == []
    assert len(relatorio.por_motivo(MOTIVO_FORMATO)) == 1


def test_zip_e_extraido(tmp_path):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as z:
        z.writestr("modulo1/aula.txt", "conteudo sobre algoritmos")
        z.writestr("modulo1/notas.txt", "isto e uma pauta")
        z.writestr("obj/Debug/gerado.cs", "class Gerado {}")
    _criar(tmp_path / "Programacao", "material.zip", memoria.getvalue())

    documentos, relatorio = carregar(tmp_path)
    assert [d.titulo for d in documentos] == ["aula"]
    assert documentos[0].disciplina == "Programacao"
    assert len(relatorio.por_motivo(MOTIVO_PRIVADO)) == 1
    assert len(relatorio.por_motivo(MOTIVO_BUILD)) == 1


def test_zip_corrompido_nao_derruba_a_carga(tmp_path):
    _criar(tmp_path / "Portugues", "quebrado.zip", b"isto nao e um zip")
    _criar(tmp_path / "Portugues", "bom.txt")
    documentos, relatorio = carregar(tmp_path)
    assert len(documentos) == 1
    assert relatorio.ignorados


def test_ficheiro_vazio_e_reportado(tmp_path):
    _criar(tmp_path / "Historia", "vazio.txt", b"   ")
    documentos, relatorio = carregar(tmp_path)
    assert documentos == []
    assert relatorio.ignorados


def test_ids_sao_sequenciais(tmp_path):
    _criar(tmp_path / "A", "um.txt")
    _criar(tmp_path / "B", "dois.txt")
    documentos, _ = carregar(tmp_path)
    assert [d.id for d in documentos] == [1, 2]


def test_disciplina_e_a_pasta_mais_proxima(tmp_path):
    # data/raw/psi9/Matematica/ficha.txt -> "Matematica", nao "psi9"
    _criar(tmp_path / "psi9" / "Matematica", "ficha.txt")
    _criar(tmp_path / "Escola", "pagina.txt")
    documentos, _ = carregar(tmp_path)
    assert {d.disciplina for d in documentos} == {"Matematica", "Escola"}
