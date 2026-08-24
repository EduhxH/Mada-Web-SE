from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.models.document import Documento
from app.search.query import buscar


def _indexar(tmp_path, documentos):
    conexao = storage.abrir(tmp_path / "i.sqlite3")
    indice, tamanhos = construir_indice(documentos)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    return conexao


def _colecao():
    return [
        Documento(1, "Ficha A", "algoritmos e ciclos", "f", "Programacao"),
        Documento(2, "Ficha B", "algoritmos e derivadas", "f", "Matematica"),
        Documento(3, "Ficha C", "ciclos de estudo", "f", "Matematica"),
    ]


def test_sem_filtro_devolve_todas_as_disciplinas(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    ids = {doc.id for doc, _ in buscar(conexao, "algoritmos")}
    assert ids == {1, 2}


def test_filtro_restringe_a_disciplina(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    ids = {doc.id for doc, _ in buscar(conexao, "algoritmos", "Matematica")}
    assert ids == {2}


def test_filtro_sem_intersecao_devolve_vazio(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    assert buscar(conexao, "derivadas", "Programacao") == []


def test_disciplina_inexistente_devolve_vazio(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    assert buscar(conexao, "algoritmos", "Astronomia") == []


def test_filtro_nao_altera_a_ordem_relativa(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    sem = [d.id for d, _ in buscar(conexao, "ciclos")]
    com = [d.id for d, _ in buscar(conexao, "ciclos", "Matematica")]
    assert com == [i for i in sem if i in com]


def test_listar_disciplinas(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    assert storage.listar_disciplinas(conexao) == ["Matematica", "Programacao"]


def test_carregar_documentos_em_lote(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    docs = storage.carregar_documentos(conexao, [1, 3])
    assert set(docs) == {1, 3}
    assert docs[1].titulo == "Ficha A"


def test_carregar_documentos_lista_vazia(tmp_path):
    conexao = _indexar(tmp_path, _colecao())
    assert storage.carregar_documentos(conexao, []) == {}


def test_ou_entra_quando_o_e_falha(tmp_path):
    from app.search.query import MODO_E, MODO_OU, buscar_detalhado

    conexao = _indexar(tmp_path, _colecao())
    # nenhum documento tem "derivadas" E "ciclos"
    r = buscar_detalhado(conexao, "derivadas ciclos")
    assert r.modo == MODO_OU
    assert {d.id for d, _ in r.documentos} == {1, 2, 3}

    # quando o E funciona, o OU nao e usado
    assert buscar_detalhado(conexao, "algoritmos ciclos").modo == MODO_E


def test_ou_ordena_quem_tem_mais_termos_primeiro(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar

    # nenhum documento tem "gama": o E falha e o OU entra.
    # Doc 1 satisfaz 2 dos 3 termos, Doc 2 apenas 1.
    conexao = _indexar(
        tmp_path,
        [
            Documento(1, "Um", "alfa beta", "f", "X"),
            Documento(2, "Dois", "alfa sozinho", "f", "X"),
            Documento(3, "Tres", "outra coisa", "f", "X"),
        ],
    )
    resultados = buscar(conexao, "alfa beta gama")
    assert [d.id for d, _ in resultados] == [1, 2]


def test_ou_nao_dispara_com_um_unico_termo(tmp_path):
    from app.search.query import MODO_VAZIO, buscar_detalhado

    conexao = _indexar(tmp_path, _colecao())
    r = buscar_detalhado(conexao, "inexistente")
    assert r.documentos == []
    assert r.modo == MODO_VAZIO


def test_permitir_ou_desligado_mantem_semantica_e(tmp_path):
    from app.search.query import buscar

    conexao = _indexar(tmp_path, _colecao())
    assert buscar(conexao, "derivadas ciclos", permitir_ou=False) == []
