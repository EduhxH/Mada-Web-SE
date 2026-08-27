from app.indexing.tokenizer import STOP_WORDS, remover_acentos, tokenizar


def test_minusculas_e_pontuacao():
    assert tokenizar("Programação, Python!") == ["programacao", "python"]


def test_remocao_de_acentos():
    assert remover_acentos("índice programação ção") == "indice programacao cao"


def test_stop_words_removidas():
    assert tokenizar("banco de dados") == ["banco", "dados"]


def test_stop_words_preservadas_quando_pedido():
    assert tokenizar("banco de dados", remover_stop_words=False) == [
        "banco",
        "de",
        "dados",
    ]


def test_duplicatas_preservadas():
    assert tokenizar("python python") == ["python", "python"]


def test_texto_vazio():
    assert tokenizar("") == []


def test_numeros_de_um_digito_sao_descartados():
    assert tokenizar("Python 3.11") == ["python", "11"]


def test_tokens_de_um_caractere_removidos():
    assert tokenizar("a C 3 programação", remover_stop_words=False) == ["programacao"]


def test_stop_words_estao_normalizadas():
    for palavra in STOP_WORDS:
        assert palavra == remover_acentos(palavra.lower())


def test_camelcase_e_separado():
    assert tokenizar("FichaRevisoes") == ["ficha", "revisoes"]
    assert tokenizar("GestCampeonato") == ["gest", "campeonato"]
    assert tokenizar("PowerPoint") == ["power", "point"]


def test_siglas_nao_sao_partidas():
    assert tokenizar("PDF") == ["pdf"]
    assert tokenizar("PSI9") == ["psi9"]
    assert tokenizar("HTML") == ["html"]


def test_camelcase_com_acentos():
    assert tokenizar("PlanificaçãoModular") == ["planificacao", "modular"]
