from app.indexing.inverted_index import construir_indice


def test_postings_corretas(documentos):
    indice, _ = construir_indice(documentos)
    assert set(indice["python"]) == {1, 3, 4}
    assert set(indice["sqlite"]) == {2}
    assert "de" not in indice


def test_frequencias_contadas(documentos):
    indice, _ = construir_indice(documentos)
    assert indice["python"][4] == 4
    assert indice["python"][1] == 1


def test_tamanhos_dos_documentos(documentos):
    _, tamanhos = construir_indice(documentos)
    # "Doc 1" + "Python e uma linguagem de programacao"
    # -> doc, python, linguagem, programacao ("1" e "de"/"uma" saem)
    assert tamanhos[1] == 4


def test_titulo_e_indexado(documentos):
    indice, _ = construir_indice(documentos)
    assert set(indice["doc"]) == {1, 2, 3, 4}


def test_disciplina_e_indexada():
    from app.models.document import Documento

    indice, _ = construir_indice(
        [Documento(1, "Ficha", "conteudo qualquer", "f", "Matematica")]
    )
    assert 1 in indice["matematica"]


def test_colecao_vazia():
    indice, tamanhos = construir_indice([])
    assert indice == {}
    assert tamanhos == {}
