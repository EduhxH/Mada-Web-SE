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


def test_numeros_sao_tokens():
    assert tokenizar("Python 3.11") == ["python", "3", "11"]


def test_stop_words_estao_normalizadas():
    for palavra in STOP_WORDS:
        assert palavra == remover_acentos(palavra.lower())
