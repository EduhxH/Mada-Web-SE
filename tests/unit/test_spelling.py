from app.search.spelling import distancia_edicao, sugerir


def test_palavras_iguais():
    assert distancia_edicao("ficha", "ficha") == 0


def test_uma_letra_a_mais():
    assert distancia_edicao("horario", "horarios") == 1


def test_uma_letra_trocada():
    assert distancia_edicao("matematica", "matemetica") == 1


def test_uma_letra_em_falta():
    assert distancia_edicao("exercicios", "exercicos") == 1


def test_duas_alteracoes():
    assert distancia_edicao("sebenta", "sebentas") <= 2


def test_palavras_muito_diferentes_excedem_o_limite():
    assert distancia_edicao("horario", "quimica", limite=2) > 2


def test_string_vazia():
    assert distancia_edicao("", "abc") == 3
    assert distancia_edicao("abc", "") == 3


def test_sugere_o_termo_mais_proximo():
    vocabulario = [("horarios", 43), ("historia", 5), ("quimica", 80)]
    assert sugerir("horario", vocabulario) == "horarios"


def test_desempata_pelo_termo_mais_frequente():
    # ambos a distancia 1 de "fichas"
    vocabulario = [("ficha", 3), ("fichar", 90)]
    assert sugerir("fichas", vocabulario) == "fichar"


def test_nao_sugere_para_termos_curtos():
    assert sugerir("psi", [("psi9", 100)]) is None


def test_nao_sugere_quando_o_termo_existe():
    assert sugerir("horarios", [("horarios", 43), ("horario", 1)]) is None


def test_sem_candidato_proximo_devolve_none():
    assert sugerir("xilofone", [("matematica", 10), ("fisica", 20)]) is None
