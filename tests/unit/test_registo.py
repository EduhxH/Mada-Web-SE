"""O registo do servidor: memoria com numero de sequencia, disco so para o que importa."""

import pytest

from app.interface import registo


@pytest.fixture(autouse=True)
def _limpar(tmp_path, monkeypatch):
    monkeypatch.setattr(registo, "CAMINHO_DISCO", tmp_path / "servidor.log")
    monkeypatch.setattr(registo._registo, "_disco_avisado", False)
    registo.limpar()
    yield
    registo.limpar()


def test_anotar_devolve_a_linha_com_numero():
    linha = registo.anotar(registo.INFO, "uma coisa", "teste")
    assert linha["texto"] == "uma coisa"
    assert linha["origem"] == "teste"
    assert linha["seq"] >= 1


def test_a_sequencia_so_cresce():
    um = registo.anotar(registo.INFO, "a")["seq"]
    dois = registo.anotar(registo.INFO, "b")["seq"]
    assert dois == um + 1


def test_desde_devolve_so_o_que_veio_depois():
    registo.anotar(registo.INFO, "antiga")
    marca = registo.ultimo_seq()
    registo.anotar(registo.INFO, "nova")
    linhas, ultimo = registo.desde(marca)
    assert [l["texto"] for l in linhas] == ["nova"]
    assert ultimo == marca + 1


def test_desde_devolve_o_ultimo_mesmo_sem_novidades():
    """Sem isto, o painel voltava a pedir do sitio errado quando o buffer roda."""
    registo.anotar(registo.INFO, "a")
    marca = registo.ultimo_seq()
    linhas, ultimo = registo.desde(marca)
    assert linhas == []
    assert ultimo == marca


def test_a_memoria_tem_tecto():
    """O tecto e estrutural: a fila tem `maxlen` e deita fora a mais antiga."""
    for numero in range(registo.MAXIMO_LINHAS + 50):
        registo.anotar(registo.INFO, f"linha {numero}")
    linhas, _ = registo.desde(0)
    assert len(linhas) == registo.MAXIMO_LINHAS
    assert linhas[0]["texto"] == "linha 50", "as primeiras cinquenta sairam"


def test_limpar_nao_reinicia_a_numeracao():
    """Se a numeracao voltasse a um, tudo o que viesse depois parecia ja visto."""
    registo.anotar(registo.INFO, "a")
    antes = registo.ultimo_seq()
    registo.limpar()
    assert registo.anotar(registo.INFO, "b")["seq"] == antes + 1


def test_nivel_desconhecido_cai_para_info():
    assert registo.anotar("inventado", "x")["nivel"] == registo.INFO


def test_texto_enorme_e_cortado():
    linha = registo.anotar(registo.INFO, "x" * (registo.LIMITE_TEXTO + 500))
    assert len(linha["texto"]) == registo.LIMITE_TEXTO


def test_contar_so_conta_os_graves():
    marca = registo.ultimo_seq()
    registo.anotar(registo.INFO, "normal")
    registo.anotar(registo.AVISO, "atencao")
    registo.anotar(registo.ERRO, "estourou")
    assert registo.contar_desde(marca) == 2
    assert registo.contar_desde(marca, (registo.INFO,)) == 1


# ------------------------------------------------------------------ disco


def test_so_os_graves_vao_ao_disco(tmp_path):
    """As linhas de pedido levam consigo o que alguem pesquisou."""
    registo.anotar(registo.INFO, "GET /?q=uma consulta privada")
    registo.anotar(registo.AVISO, "algo estranho")
    texto = (tmp_path / "servidor.log").read_text(encoding="utf-8")
    assert "algo estranho" in texto
    assert "uma consulta privada" not in texto


def test_o_erro_leva_a_pilha_inteira():
    try:
        raise ValueError("rebentou aqui")
    except ValueError:
        linha = registo.excecao("a fazer uma coisa", "teste")
    assert "a fazer uma coisa" in linha["texto"]
    assert "ValueError" in linha["texto"]
    assert linha["nivel"] == registo.ERRO


def test_disco_sem_permissao_nao_derruba_o_servidor(tmp_path, monkeypatch):
    def recusa(*a, **k):
        raise OSError("sem permissao")

    monkeypatch.setattr(registo.Path, "mkdir", recusa)
    registo.anotar(registo.ERRO, "isto tem de continuar a funcionar")
    linhas, _ = registo.desde(0)
    textos = [l["texto"] for l in linhas]
    assert "isto tem de continuar a funcionar" in textos
    assert any("nao consigo escrever" in t for t in textos)


def test_o_aviso_de_disco_e_dado_uma_vez(tmp_path, monkeypatch):
    def recusa(*a, **k):
        raise OSError("sem permissao")

    monkeypatch.setattr(registo.Path, "mkdir", recusa)
    for _ in range(5):
        registo.anotar(registo.ERRO, "erro")
    linhas, _ = registo.desde(0)
    quantos = sum(1 for l in linhas if "nao consigo escrever" in l["texto"])
    assert quantos == 1


def test_o_ficheiro_roda_quando_cresce(tmp_path, monkeypatch):
    monkeypatch.setattr(registo, "BYTES_MAXIMOS_DISCO", 50)
    caminho = tmp_path / "servidor.log"
    caminho.write_text("x" * 200, encoding="utf-8")
    registo.anotar(registo.ERRO, "linha nova")
    assert (tmp_path / "servidor.log.1").read_text(encoding="utf-8") == "x" * 200
    assert "linha nova" in caminho.read_text(encoding="utf-8")


# ------------------------------------------------------------------ canal


def test_o_canal_parte_a_saida_em_linhas():
    """As rotinas comunicam com `print`; o canal transforma isso em registo."""
    marca = registo.ultimo_seq()
    canal = registo.Canal("operacao")
    canal.write("primeira\nsegunda\n")
    linhas, _ = registo.desde(marca)
    assert [l["texto"] for l in linhas] == ["primeira", "segunda"]
    assert all(l["origem"] == "operacao" for l in linhas)


def test_o_canal_guarda_a_linha_incompleta_ate_ao_fim():
    marca = registo.ultimo_seq()
    canal = registo.Canal("operacao")
    canal.write("come")
    canal.write("cou e ")
    assert registo.desde(marca)[0] == []
    canal.write("acabou\n")
    assert [l["texto"] for l in registo.desde(marca)[0]] == ["comecou e acabou"]


def test_o_canal_despeja_o_que_sobra_no_flush():
    marca = registo.ultimo_seq()
    canal = registo.Canal("operacao")
    canal.write("sem mudanca de linha no fim")
    canal.flush()
    assert [l["texto"] for l in registo.desde(marca)[0]] == [
        "sem mudanca de linha no fim"
    ]


def test_o_canal_ignora_linhas_vazias():
    marca = registo.ultimo_seq()
    canal = registo.Canal("operacao")
    canal.write("\n\n   \n")
    assert registo.desde(marca)[0] == []


def test_o_canal_serve_de_stdout():
    import contextlib

    marca = registo.ultimo_seq()
    canal = registo.Canal("operacao")
    with contextlib.redirect_stdout(canal):
        print("dito por print")
    canal.flush()
    assert [l["texto"] for l in registo.desde(marca)[0]] == ["dito por print"]
