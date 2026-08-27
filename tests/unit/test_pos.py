import pytest

from app.indexing import pos


@pytest.mark.parametrize(
    "palavra",
    ["reconhecer", "propor", "interpretar", "explorar", "contribuir", "analisar",
     "calcular", "resolver", "distinguir", "compor"],
)
def test_infinitivos_sao_verbos(palavra):
    assert pos.classificar(palavra) == pos.INFINITIVO
    assert not pos.serve_como_tema(palavra)


@pytest.mark.parametrize(
    "palavra", ["recorrendo", "utilizando", "resolvendo", "definindo"]
)
def test_gerundios(palavra):
    assert pos.classificar(palavra) == pos.GERUNDIO
    assert not pos.serve_como_tema(palavra)


@pytest.mark.parametrize(
    "palavra", ["normalizada", "identificados", "definido", "aplicadas"]
)
def test_participios(palavra):
    assert pos.classificar(palavra) == pos.PARTICIPIO
    assert not pos.serve_como_tema(palavra)


@pytest.mark.parametrize("palavra", ["rapidamente", "corretamente", "principalmente"])
def test_adverbios(palavra):
    assert pos.classificar(palavra) == pos.ADVERBIO
    assert not pos.serve_como_tema(palavra)


@pytest.mark.parametrize("palavra", ["identificaram", "utilizassem", "resolveriam"])
def test_conjugados(palavra):
    assert pos.classificar(palavra) == pos.CONJUGADO
    assert not pos.serve_como_tema(palavra)


@pytest.mark.parametrize(
    "palavra",
    ["radiacao", "temperatura", "geometria", "cantigas", "energia", "onda",
     "espectro", "termodinamica", "personagens"],
)
def test_temas_reais_sobrevivem(palavra):
    assert pos.serve_como_tema(palavra)


@pytest.mark.parametrize(
    "palavra",
    ["professor", "lugar", "calor", "valor", "motor", "escolar", "computador",
     "celular", "circular", "mulher", "superior", "interior"],
)
def test_nomes_com_terminacao_de_verbo_nao_sao_despromovidos(palavra):
    assert pos.serve_como_tema(palavra), f"{palavra} devia contar como nome"


@pytest.mark.parametrize(
    "palavra", ["estado", "resultado", "dados", "conteudo", "metodo", "periodo",
                "derivadas", "velocidade", "sentido", "liquido"]
)
def test_nomes_com_terminacao_de_participio(palavra):
    assert pos.serve_como_tema(palavra), f"{palavra} devia contar como nome"


def test_palavras_curtas_nao_sao_classificadas_como_verbo():
    assert pos.serve_como_tema("mar")
    assert pos.serve_como_tema("cor")


def test_acentos_nao_alteram_a_classificacao():
    assert pos.classificar("análise") == pos.classificar("analise")
    assert pos.classificar("própor") == pos.classificar("propor")
