from app.analytics import uso


def _registo(tmp_path):
    return uso.abrir(tmp_path / "uso.sqlite3")


def test_resumo_de_base_vazia(tmp_path):
    dados = uso.resumo(_registo(tmp_path))
    assert dados["buscas"] == 0
    assert dados["taxa_vazias"] == 0.0
    assert dados["taxa_abertura"] == 0.0


def test_conta_buscas_e_participantes(tmp_path):
    conexao = _registo(tmp_path)
    uso.registar(conexao, "aluno-01", uso.EVENTO_BUSCA, consulta="ficha", resultados=3)
    uso.registar(conexao, "aluno-02", uso.EVENTO_BUSCA, consulta="teste", resultados=0)
    dados = uso.resumo(conexao)
    assert dados["buscas"] == 2
    assert dados["participantes"] == 2
    assert dados["taxa_vazias"] == 50.0


def test_taxa_de_abertura(tmp_path):
    conexao = _registo(tmp_path)
    for _ in range(4):
        uso.registar(conexao, "aluno-01", uso.EVENTO_BUSCA, consulta="x", resultados=2)
    uso.registar(conexao, "aluno-01", uso.EVENTO_ABERTURA, doc_id=7, posicao=1)
    dados = uso.resumo(conexao)
    assert dados["aberturas"] == 1
    assert dados["taxa_abertura"] == 25.0


def test_taxa_de_parciais(tmp_path):
    conexao = _registo(tmp_path)
    uso.registar(conexao, "a", uso.EVENTO_BUSCA, consulta="x", resultados=5, modo="ou")
    uso.registar(conexao, "a", uso.EVENTO_BUSCA, consulta="y", resultados=5, modo="e")
    assert uso.resumo(conexao)["taxa_parciais"] == 50.0


def test_consultas_populares_agrupam_por_caixa(tmp_path):
    conexao = _registo(tmp_path)
    for consulta in ["Ficha", "ficha", "FICHA", "teste"]:
        uso.registar(conexao, "a", uso.EVENTO_BUSCA, consulta=consulta, resultados=1)
    populares = uso.consultas_populares(conexao)
    assert populares[0][1] == 3


def test_consultas_sem_resultado(tmp_path):
    conexao = _registo(tmp_path)
    uso.registar(conexao, "a", uso.EVENTO_BUSCA, consulta="inexistente", resultados=0)
    uso.registar(conexao, "a", uso.EVENTO_BUSCA, consulta="existente", resultados=4)
    falhadas = uso.consultas_sem_resultado(conexao)
    assert [c for c, _ in falhadas] == ["inexistente"]


def test_por_participante(tmp_path):
    conexao = _registo(tmp_path)
    uso.registar(conexao, "aluno-01", uso.EVENTO_BUSCA, consulta="x", resultados=1)
    uso.registar(conexao, "aluno-01", uso.EVENTO_ABERTURA, doc_id=1)
    uso.registar(conexao, "aluno-02", uso.EVENTO_BUSCA, consulta="y", resultados=1)
    linhas = {p: (b, a) for p, b, a in uso.por_participante(conexao)}
    assert linhas["aluno-01"] == (1, 1)
    assert linhas["aluno-02"] == (1, 0)


def test_pagina_de_estatisticas_gera_html(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    uso.registar(conexao, "aluno-01", uso.EVENTO_BUSCA, consulta="ficha", resultados=2)
    pagina = estatisticas.pagina(conexao)
    assert "<svg" in pagina
    assert "estatisticas" in pagina
    assert "aluno-01" in pagina


def test_pagina_escapa_consultas(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    uso.registar(
        conexao, "a", uso.EVENTO_BUSCA, consulta="<script>x</script>", resultados=0
    )
    pagina = estatisticas.pagina(conexao)
    assert "<script>x</script>" not in pagina
    assert "&lt;script&gt;" in pagina
