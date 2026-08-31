from app.indexing.tokenizer import tokenizar
from app.search import siglas


def termos(consulta):
    return set(tokenizar(consulta))


def test_sigla_escrita_e_reconhecida():
    encontrados = siglas.detetar(termos("criterios de fct"))
    assert [s for s, _, _ in encontrados] == ["fct"]


def test_expressao_por_extenso_e_reconhecida():
    """O documento diz "FCT"; o aluno escreveu tudo."""
    encontrados = siglas.detetar(termos("formacao em contexto de trabalho"))
    assert [s for s, _, _ in encontrados] == ["fct"]


def test_meia_expressao_nao_conta():
    """"trabalho" sozinho nao pode virar TPC: esta em 554 documentos."""
    assert siglas.detetar(termos("trabalho de portugues")) == []
    assert siglas.detetar(termos("formacao de adultos")) == []


def test_consumo_da_sigla_e_o_proprio_termo():
    _, _, consumidos = siglas.detetar(termos("tpc"))[0]
    assert consumidos == {"tpc"}


def test_consumo_da_expressao_sao_as_palavras_dela():
    _, _, consumidos = siglas.detetar(termos("trabalho para casa"))[0]
    assert consumidos == {"trabalho", "casa"}


def test_expansoes_passam_pelo_tokenizer_do_indice():
    """As palavras vazias e os acentos tem de sair do mesmo modo que no indice."""
    _, palavras, _ = siglas.detetar(termos("prova de aptidao profissional"))[0]
    assert "de" not in palavras
    assert "aptidao" in palavras


def test_consulta_sem_siglas():
    assert siglas.detetar(termos("calendario escolar")) == []


def test_conceito_funde_a_sigla_com_a_expressao(tmp_path):
    """O termo passa a valer os documentos das duas formas."""
    from app.indexing import storage
    from app.indexing.inverted_index import construir_indice
    from app.models.document import Documento
    from app.search import query

    documentos = [
        Documento(1, "Com sigla", "o FCT decorre numa empresa", "a", ""),
        Documento(2, "Por extenso", "a formacao em contexto de trabalho e obrigatoria", "b", ""),
        Documento(3, "Nem uma nem outra", "trabalho de grupo sobre historia", "c", ""),
    ]
    indice, tamanhos = construir_indice(documentos)
    conexao = storage.abrir(tmp_path / "i.sqlite3")
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    query.limpar_cache()

    for consulta in ("fct", "formacao em contexto de trabalho"):
        encontrados = {d.id for d, _ in query.buscar_detalhado(conexao, consulta).documentos}
        assert {1, 2} <= encontrados, (consulta, encontrados)
        assert 3 not in encontrados, consulta
    query.limpar_cache()
