from app.search import morfologia

VOCAB = {
    "horario", "horarios", "ficha", "fichas", "criterio", "criterios",
    "licao", "licoes", "papel", "papeis", "homem", "homens",
    "professor", "professores", "luz", "luzes", "psi9", "onda", "ondas",
}


def test_plural_simples():
    assert morfologia.variantes("ficha", VOCAB) == {"ficha", "fichas"}


def test_singular_a_partir_do_plural():
    assert morfologia.variantes("fichas", VOCAB) == {"ficha", "fichas"}


def test_plural_em_oes():
    assert morfologia.variantes("licao", VOCAB) == {"licao", "licoes"}
    assert morfologia.variantes("licoes", VOCAB) == {"licao", "licoes"}


def test_plural_de_palavra_em_l():
    assert morfologia.variantes("papel", VOCAB) == {"papel", "papeis"}
    assert morfologia.variantes("papeis", VOCAB) == {"papel", "papeis"}


def test_plural_de_palavra_em_m():
    assert morfologia.variantes("homem", VOCAB) == {"homem", "homens"}


def test_plural_de_palavra_em_r_e_z():
    assert morfologia.variantes("professor", VOCAB) == {"professor", "professores"}
    assert morfologia.variantes("luz", VOCAB) == {"luz", "luzes"}


def test_nao_expande_para_fora_do_vocabulario():
    # "psi9s" nao existe: nada e inventado
    assert morfologia.variantes("psi9", VOCAB) == {"psi9"}
    assert morfologia.variantes("inexistente", VOCAB) == {"inexistente"}


def test_termos_curtos_nao_sao_expandidos():
    assert morfologia.variantes("as", {"as", "ase"}) == {"as"}
    assert morfologia.variantes("de", {"de", "des"}) == {"de"}


def test_expandir_devolve_um_conjunto_por_termo():
    resultado = morfologia.expandir({"ficha", "psi9"}, VOCAB)
    assert resultado["ficha"] == {"ficha", "fichas"}
    assert resultado["psi9"] == {"psi9"}


def test_vocabulario_vazio_nao_expande():
    assert morfologia.variantes("ficha", set()) == {"ficha"}


def test_limite_de_variantes():
    vocab = {"licao", "licoes", "licaos", "licaes"}
    assert len(morfologia.variantes("licao", vocab)) <= morfologia.MAXIMO_VARIANTES
