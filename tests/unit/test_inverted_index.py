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
    assert tamanhos[1] == 3


def test_colecao_vazia():
    indice, tamanhos = construir_indice([])
    assert indice == {}
    assert tamanhos == {}
