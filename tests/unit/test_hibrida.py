from app.search import hibrida


def _lex(*ids):
    return [(doc_id, 1.0 / (i + 1)) for i, doc_id in enumerate(ids)]


def test_documento_nas_duas_listas_sobe():
    """O sinal de duas fontes independentes vale mais que o de uma."""
    fusao = hibrida.fundir(_lex(1, 2, 3), {2: 0.9})
    assert fusao.documentos[0][0] == 2
    assert fusao.em_ambas == 1


def test_semantico_puro_entra_na_lista():
    """O caso que motivou tudo: a parafrase que o lexical nao ve."""
    fusao = hibrida.fundir(_lex(1), {99: 0.8})
    assert 99 in dict(fusao.documentos)
    assert fusao.so_semantico == 1


def test_piso_corta_semelhanca_fraca():
    fusao = hibrida.fundir(_lex(1), {99: 0.2})
    assert 99 not in dict(fusao.documentos)
    assert not fusao.usou_semantica


def test_sem_semantica_devolve_a_ordem_lexical():
    fusao = hibrida.fundir(_lex(5, 6, 7), {})
    assert [d for d, _ in fusao.documentos] == [5, 6, 7]
    assert not fusao.usou_semantica


def test_sem_lexical_devolve_a_ordem_semantica():
    fusao = hibrida.fundir([], {8: 0.9, 9: 0.6})
    assert [d for d, _ in fusao.documentos] == [8, 9]


def test_ordem_semantica_respeita_a_semelhanca():
    fusao = hibrida.fundir([], {1: 0.5, 2: 0.95, 3: 0.7})
    assert [d for d, _ in fusao.documentos] == [2, 3, 1]


def test_duas_listas_vazias():
    fusao = hibrida.fundir([], {})
    assert fusao.documentos == []


def test_fusao_e_por_posicao_nao_por_pontuacao():
    """Pontuacoes lexicais minusculas nao devem perder para o cosseno so por
    serem de outra escala: e a posicao que conta."""
    minusculas = [(1, 0.0001), (2, 0.00005)]
    fusao = hibrida.fundir(minusculas, {2: 0.99})
    assert fusao.documentos[0][0] == 2  # 2 esta nas duas listas
    assert dict(fusao.documentos)[1] > 0  # 1 nao foi esmagado
