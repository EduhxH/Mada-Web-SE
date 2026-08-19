from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.search.naive import buscar_ingenua
from app.search.query import buscar


def _indexar(tmp_path, documentos):
    caminho = tmp_path / "indice.sqlite3"
    conexao = storage.abrir(caminho)
    indice, tamanhos = construir_indice(documentos)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    return caminho, conexao


def test_indice_concorda_com_oraculo(tmp_path, documentos):
    _, conexao = _indexar(tmp_path, documentos)
    consultas = [
        "python",
        "python programação",
        "banco de dados",
        "PYTHON",
        "golang",
        "python sqlite",
        "",
    ]
    for consulta in consultas:
        esperado = {d.id for d in buscar_ingenua(consulta, documentos)}
        obtido = {doc.id for doc, _ in buscar(conexao, consulta)}
        assert obtido == esperado, f"divergencia na consulta: {consulta!r}"


def test_ranqueamento_prefere_doc_repetitivo(tmp_path, documentos):
    _, conexao = _indexar(tmp_path, documentos)
    resultados = buscar(conexao, "python")
    assert resultados[0][0].id == 4


def test_indice_sobrevive_a_reabertura(tmp_path, documentos):
    caminho, conexao = _indexar(tmp_path, documentos)
    conexao.close()
    reaberta = storage.abrir(caminho)
    resultados = buscar(reaberta, "sqlite")
    assert [doc.id for doc, _ in resultados] == [2]
