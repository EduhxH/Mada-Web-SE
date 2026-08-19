from app.search.ranker import pontuar


def test_termo_raro_vale_mais_que_termo_comum():
    postings = {"python": {1: 1, 2: 1}, "sqlite": {2: 1}}
    tamanhos = {1: 10, 2: 10}
    ranque = pontuar(postings, {1, 2}, tamanhos, total_docs=2)
    assert ranque[0][0] == 2


def test_frequencia_maior_pontua_mais():
    postings = {"python": {1: 1, 2: 5}}
    tamanhos = {1: 10, 2: 10}
    ranque = pontuar(postings, {1, 2}, tamanhos, total_docs=3)
    assert ranque[0][0] == 2


def test_documento_longo_nao_vence_so_por_ser_longo():
    postings = {"python": {1: 2, 2: 2}}
    tamanhos = {1: 10, 2: 100}
    ranque = pontuar(postings, {1, 2}, tamanhos, total_docs=3)
    assert ranque[0][0] == 1


def test_ordem_decrescente_e_todos_presentes():
    postings = {"a": {1: 1, 2: 2, 3: 3}}
    tamanhos = {1: 10, 2: 10, 3: 10}
    ranque = pontuar(postings, {1, 2, 3}, tamanhos, total_docs=5)
    pontuacoes = [p for _, p in ranque]
    assert pontuacoes == sorted(pontuacoes, reverse=True)
    assert {doc_id for doc_id, _ in ranque} == {1, 2, 3}
