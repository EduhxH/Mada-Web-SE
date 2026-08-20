from app.search.snippet import gerar_trecho


def test_trecho_centrado_no_termo():
    texto = (
        " ".join(f"antes{i}" for i in range(50))
        + " python "
        + " ".join(f"depois{i}" for i in range(50))
    )
    trecho = gerar_trecho(texto, {"python"}, raio=3)
    assert "python" in trecho
    assert trecho.startswith("...")
    assert trecho.endswith("...")


def test_termo_ausente_usa_o_inicio():
    trecho = gerar_trecho("um dois tres quatro", {"zzz"}, raio=2)
    assert trecho.startswith("um")


def test_casa_com_acento_e_pontuacao_do_original():
    trecho = gerar_trecho("A Programação! é linda", {"programacao"}, raio=1)
    assert "Programação!" in trecho
