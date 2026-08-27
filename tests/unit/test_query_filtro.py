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
    # Doc 1 satisfaz 2 de 3 termos e passa o quorum; Doc 2 so satisfaz 1.
    resultados = buscar(conexao, "alfa beta gama")
    assert [d.id for d, _ in resultados] == [1]


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


def _colecao_quorum():
    from app.models.document import Documento

    return [
        Documento(1, "Tres", "alfa beta gama juntos", "f", "X"),
        Documento(2, "Dois", "alfa beta apenas", "f", "X"),
        Documento(3, "Um", "alfa sozinho aqui", "f", "X"),
        Documento(4, "Zero", "nada relacionado", "f", "X"),
    ]


def test_modo_e_quando_um_documento_tem_tudo(tmp_path):
    from app.search.query import MODO_E, buscar_detalhado

    conexao = _indexar(tmp_path, _colecao_quorum())
    r = buscar_detalhado(conexao, "alfa beta gama")
    assert r.modo == MODO_E
    assert [d.id for d, _ in r.documentos] == [1]
    assert r.termos_exigidos == 3


def test_quorum_entra_quando_o_e_falha(tmp_path):
    from app.search.query import MODO_QUORUM, buscar_detalhado

    conexao = _indexar(tmp_path, _colecao_quorum())
    # "delta" nao existe: nenhum documento tem os 4 termos
    r = buscar_detalhado(conexao, "alfa beta gama delta")
    assert r.modo == MODO_QUORUM
    assert r.termos_exigidos >= 2
    # doc 3 tem so "alfa": fica de fora
    assert 3 not in [d.id for d, _ in r.documentos]


def test_ou_como_ultimo_recurso(tmp_path):
    from app.search.query import MODO_OU, buscar_detalhado

    conexao = _indexar(tmp_path, _colecao_quorum())
    # so "alfa" existe; nenhum documento chega ao quorum de 2
    r = buscar_detalhado(conexao, "alfa zzz yyy")
    assert r.modo == MODO_OU
    assert r.termos_exigidos == 1
    assert {d.id for d, _ in r.documentos} == {1, 2, 3}


def test_quorum_respeita_o_filtro_de_disciplina(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar

    docs = _colecao_quorum() + [
        Documento(5, "Outra", "alfa beta gama", "f", "Y"),
    ]
    conexao = _indexar(tmp_path, docs)
    ids = {d.id for d, _ in buscar(conexao, "alfa beta gama delta", "Y")}
    assert ids == {5}


def test_correcao_automatica_de_gralha(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar_detalhado

    docs = [
        Documento(n, f"Doc {n}", "matematica exercicios resolvidos", "f", "X")
        for n in range(1, 6)
    ]
    conexao = _indexar(tmp_path, docs)
    r = buscar_detalhado(conexao, "matematca")
    assert r.correcao == {"matematca": "matematica"}
    assert r.documentos


def test_correcao_nao_e_aplicada_se_a_palavra_for_rara(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar_detalhado

    docs = [Documento(1, "Doc", "matematica unica", "f", "X")]
    docs += [Documento(n, f"D {n}", "outro conteudo", "f", "X") for n in range(2, 6)]
    conexao = _indexar(tmp_path, docs)
    r = buscar_detalhado(conexao, "matematca")
    # so 1 documento tem "matematica": fica como sugestao, nao correcao
    assert r.correcao == {}
    assert r.sugestoes.get("matematca") == "matematica"


def test_permitir_ou_desligado_nao_corrige_nem_relaxa(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar_detalhado

    docs = [
        Documento(n, f"Doc {n}", "matematica exercicios", "f", "X")
        for n in range(1, 6)
    ]
    conexao = _indexar(tmp_path, docs)
    r = buscar_detalhado(conexao, "matematca", permitir_ou=False)
    assert r.correcao == {}
    assert r.documentos == []


def test_acerto_no_titulo_sobe_no_ranque(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar

    docs = [
        Documento(1, "Notas soltas", "regulamento mencionado de passagem aqui", "f", "X"),
        Documento(2, "Regulamento Interno", "texto sobre normas e deveres", "f", "X"),
        Documento(3, "Outro", "conteudo diferente", "f", "X"),
    ]
    conexao = _indexar(tmp_path, docs)
    assert [d.id for d, _ in buscar(conexao, "regulamento")][0] == 2


def test_realce_nao_inventa_resultados(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar

    docs = [
        Documento(1, "Regulamento", "texto", "f", "X"),
        Documento(2, "Outro", "nada", "f", "X"),
    ]
    conexao = _indexar(tmp_path, docs)
    assert {d.id for d, _ in buscar(conexao, "regulamento")} == {1}


def test_expansao_encontra_o_plural(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar, limpar_cache

    docs = [
        Documento(n, f"Doc {n}", "os criterios de avaliacao do modulo", "f", "X")
        for n in range(1, 6)
    ]
    conexao = _indexar(tmp_path, docs)
    limpar_cache()
    # pesquisa no singular, documentos so tem o plural
    assert len(buscar(conexao, "criterio")) == 5


def test_expansao_encontra_o_singular(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar, limpar_cache

    docs = [
        Documento(n, f"Doc {n}", "o horario desta turma", "f", "X")
        for n in range(1, 6)
    ]
    conexao = _indexar(tmp_path, docs)
    limpar_cache()
    assert len(buscar(conexao, "horarios")) == 5


def test_expansao_nao_inventa_resultados(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar, limpar_cache

    docs = [
        Documento(1, "A", "conteudo sobre gatos", "f", "X"),
        Documento(2, "B", "conteudo sobre carros", "f", "X"),
    ]
    conexao = _indexar(tmp_path, docs)
    limpar_cache()
    assert buscar(conexao, "aviao") == []


def test_expansao_desligada_com_exato(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar, limpar_cache

    docs = [
        Documento(n, f"Doc {n}", "os criterios definidos", "f", "X")
        for n in range(1, 6)
    ]
    conexao = _indexar(tmp_path, docs)
    limpar_cache()
    assert buscar(conexao, "criterio", permitir_ou=False) == []


def test_realce_de_titulo_usa_as_variantes(tmp_path):
    from app.models.document import Documento
    from app.search.query import buscar, limpar_cache

    docs = [
        Documento(1, "Notas gerais", "menciona horarios uma vez", "f", "X"),
        Documento(2, "Horarios da escola", "tabela com aulas e salas", "f", "X"),
        Documento(3, "Outro", "horarios tambem aqui algures", "f", "X"),
    ] + [
        # sem estes, o termo estaria em 100% dos documentos e o IDF seria 0
        Documento(n, f"Sem relacao {n}", "conteudo completamente diferente", "f", "X")
        for n in range(4, 9)
    ]
    conexao = _indexar(tmp_path, docs)
    limpar_cache()
    # consulta no singular: o titulo tem o plural e deve pesar na mesma
    assert [d.id for d, _ in buscar(conexao, "horario")][0] == 2
