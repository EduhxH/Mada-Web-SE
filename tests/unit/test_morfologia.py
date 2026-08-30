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


VOCAB_GRAFIA = {
    "adotados", "adoptados", "atividades", "actividades",
    "objetivo", "objectivo", "protecao", "proteccao",
    "percecao", "percepcao", "apto", "ato", "atos",
}


def test_grafia_nova_encontra_a_antiga():
    """Os documentos da escola sao anteriores ao acordo de 1990; os alunos nao."""
    assert "adoptados" in morfologia.variantes("adotados", VOCAB_GRAFIA)
    assert "actividades" in morfologia.variantes("atividades", VOCAB_GRAFIA)
    assert "objectivo" in morfologia.variantes("objetivo", VOCAB_GRAFIA)


def test_grafia_antiga_encontra_a_nova():
    assert "adotados" in morfologia.variantes("adoptados", VOCAB_GRAFIA)
    assert "atividades" in morfologia.variantes("actividades", VOCAB_GRAFIA)


def test_consoante_muda_antes_de_c_e_cedilha():
    assert "proteccao" in morfologia.variantes("protecao", VOCAB_GRAFIA)
    assert "percepcao" in morfologia.variantes("percecao", VOCAB_GRAFIA)


def test_palavras_curtas_nao_colidem():
    """"apto" e "ato" sao palavras diferentes: o p nao e mudo."""
    assert morfologia.variantes("apto", VOCAB_GRAFIA) == {"apto"}
    assert "apto" not in morfologia.variantes("ato", VOCAB_GRAFIA)


def test_grafia_nao_inventa_palavras():
    """A regra propoe, o vocabulario decide - como no resto do modulo."""
    assert morfologia.variantes("atividades", {"atividades"}) == {"atividades"}
