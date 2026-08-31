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


def test_digitos_soltos_sao_guardados():
    """Decisao invertida: a escola organiza-se por modulos, e "modulo 3"
    perdia justamente o 3 - a parte que distinguia a consulta."""
    assert tokenizar("Python 3.11") == ["python", "3", "11"]
    assert tokenizar("modulo 3 de fisica") == ["modulo", "3", "fisica"]


def test_letras_soltas_continuam_a_cair():
    """O comprimento minimo existe para letras: uma nao diz nada."""
    assert tokenizar("a C programação", remover_stop_words=False) == ["programacao"]


def test_ordinal_reduz_ao_numero():
    """"10o ano" e "10 ano" tem de casar: o corpus escreve um, o aluno o outro."""
    assert tokenizar("MANUAIS ADOPTADOS 10º ano") == ["manuais", "adoptados", "10", "ano"]
    assert tokenizar("manuais adotados 10 ano") == ["manuais", "adotados", "10", "ano"]


def test_camel_nao_parte_digito_de_letra():
    """"3D" nao e camelCase; parti-lo deixava so o "3"."""
    assert tokenizar("modelação 3D") == ["modelacao", "3d"]
    assert tokenizar("FichaRevisoes") == ["ficha", "revisoes"]


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


def test_palavras_de_pergunta_saem():
    """O aluno escreve uma pergunta; o assunto dela e o que fica."""
    assert tokenizar("quantas faltas posso ter") == ["faltas"]
    assert tokenizar("onde vejo o meu horario") == ["horario"]
    assert tokenizar("quais sao os criterios de avaliacao") == [
        "criterios", "avaliacao"
    ]


def test_interrogativas_nao_decidem_a_busca():
    """Sao raras no corpus - "vejo" em 1 documento, "posso" em 5 - e o TF-IDF
    premeia o que e raro. Sem isto, decidiam a resposta."""
    from app.indexing.tokenizer import PALAVRAS_DE_PERGUNTA, STOP_WORDS

    for palavra in ("quando", "onde", "quantas", "posso", "vejo", "tenho"):
        assert palavra in PALAVRAS_DE_PERGUNTA
        assert palavra in STOP_WORDS


def test_o_assunto_da_pergunta_sobrevive():
    """Tirar o enquadramento nao pode levar o assunto atras."""
    for consulta, esperado in (
        ("quando comecam as aulas", {"comecam", "aulas"}),
        ("como funciona o exame de recuperacao", {"funciona", "exame", "recuperacao"}),
        ("onde estao as fichas de portugues", {"fichas", "portugues"}),
    ):
        assert set(tokenizar(consulta)) == esperado


def test_consulta_so_de_enquadramento_fica_vazia():
    """Nao ha assunto nenhum: melhor nada do que ruido."""
    assert tokenizar("onde posso ver") == []
