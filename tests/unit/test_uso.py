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
    assert "estatisticas" in pagina
    assert "1" in pagina  # o cartao das buscas
    # Com um dia so nao ha grafico: uma barra sozinha nao compara nada.
    # Procura-se <rect> e nao <svg>: a pagina tem sempre SVG, que e como os
    # icones sao desenhados; barras so as tem o grafico.
    assert "<rect" not in pagina


def test_grafico_aparece_quando_ha_dias_que_cheguem(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    for dia in ("2026-09-15", "2026-09-16", "2026-09-17"):
        conexao.execute(
            "INSERT INTO eventos (momento, dia, participante, tipo, consulta,"
            " resultados) VALUES (?,?,?,?,?,?)",
            (f"{dia}T10:00:00+00:00", dia, "aluno-01", uso.EVENTO_BUSCA, "x", 1),
        )
    conexao.commit()
    assert "<svg" in estatisticas.pagina(conexao)


def test_pagina_escapa_consultas(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    for aluno in ("a", "b"):
        uso.registar(
            conexao, aluno, uso.EVENTO_BUSCA,
            consulta="<script>x</script>", resultados=0,
        )
    pagina = estatisticas.pagina(conexao, administrador=True)
    assert "<script>x</script>" not in pagina
    assert "&lt;script&gt;" in pagina


def test_participante_nao_ve_consultas_de_um_so_colega(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    uso.registar(
        conexao, "aluno-02", uso.EVENTO_BUSCA,
        consulta="assunto pessoal dele", resultados=0,
    )
    normal = estatisticas.pagina(conexao)
    assert "assunto pessoal dele" not in normal
    # o administrador precisa do dado completo para a investigacao
    assert "assunto pessoal dele" in estatisticas.pagina(conexao, administrador=True)


def test_participante_nao_ve_a_tabela_por_participante(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    uso.registar(conexao, "aluno-07", uso.EVENTO_BUSCA, consulta="x", resultados=1)
    assert "aluno-07" not in estatisticas.pagina(conexao)
    assert "aluno-07" in estatisticas.pagina(conexao, administrador=True)


def test_consulta_de_dois_participantes_e_visivel(tmp_path):
    from app.interface import estatisticas

    conexao = _registo(tmp_path)
    for aluno in ("aluno-01", "aluno-02"):
        uso.registar(
            conexao, aluno, uso.EVENTO_BUSCA, consulta="ficha comum", resultados=0
        )
    assert "ficha comum" in estatisticas.pagina(conexao)


def test_grafico_nao_se_desenha_com_poucos_dias(tmp_path):
    """Uma barra sozinha a ocupar a altura toda parece avaria, nao informacao."""
    from app.interface import estatisticas

    with_um = estatisticas._barras([("2026-09-15", 62)], "Buscas por dia")
    assert "<svg" not in with_um
    assert "62" in with_um and "2026-09-15" in with_um

    com_tres = estatisticas._barras(
        [("d1", 5), ("d2", 9), ("d3", 2)], "Buscas por dia"
    )
    assert "<svg" in com_tres


def test_grafico_sem_dados_continua_a_dizer_isso(tmp_path):
    from app.interface import estatisticas

    assert "Sem dados ainda" in estatisticas._barras([], "Buscas por dia")


def test_resumo_curto_escapa_rotulos():
    from app.interface import estatisticas

    saida = estatisticas._barras([("<script>", 3)], "T")
    assert "<script>" not in saida
    assert "&lt;script&gt;" in saida
