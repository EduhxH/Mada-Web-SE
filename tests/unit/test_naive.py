from app.search.naive import buscar_ingenua


def test_termo_unico(documentos):
    ids = [d.id for d in buscar_ingenua("python", documentos)]
    assert ids == [1, 3, 4]


def test_logica_e(documentos):
    ids = [d.id for d in buscar_ingenua("python programação", documentos)]
    assert ids == [1, 3]


def test_consulta_normalizada_como_documento(documentos):
    assert buscar_ingenua("PYTHON", documentos) == buscar_ingenua("python", documentos)
    assert buscar_ingenua("programacao", documentos) == buscar_ingenua(
        "programação", documentos
    )


def test_termo_inexistente(documentos):
    assert buscar_ingenua("golang", documentos) == []


def test_consulta_vazia_ou_so_stop_words(documentos):
    assert buscar_ingenua("", documentos) == []
    assert buscar_ingenua("de e a", documentos) == []
