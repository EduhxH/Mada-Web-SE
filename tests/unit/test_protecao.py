import pytest

from app.interface import protecao


class _CabecalhosFalsos(dict):
    def get(self, chave, omissao=None):
        return dict.get(self, chave, omissao)


class _PedidoFalso:
    def __init__(self, endereco, cabecalhos=None):
        self.client_address = (endereco, 12345)
        self.headers = _CabecalhosFalsos(cabecalhos or {})


def test_limitador_deixa_passar_ate_ao_maximo():
    limitador = protecao.Limitador(maximo=3, janela=60)
    assert all(limitador.permitir("1.2.3.4") for _ in range(3))
    assert not limitador.permitir("1.2.3.4")


def test_limitador_separa_por_endereco():
    limitador = protecao.Limitador(maximo=1, janela=60)
    assert limitador.permitir("1.1.1.1")
    assert not limitador.permitir("1.1.1.1")
    assert limitador.permitir("2.2.2.2")


def test_limitador_esquece_apos_a_janela(monkeypatch):
    limitador = protecao.Limitador(maximo=1, janela=10)
    tempo = [1000.0]
    monkeypatch.setattr(protecao.time, "monotonic", lambda: tempo[0])
    assert limitador.permitir("1.1.1.1")
    assert not limitador.permitir("1.1.1.1")
    tempo[0] += 11
    assert limitador.permitir("1.1.1.1")


def test_limpar_reinicia_a_contagem():
    limitador = protecao.Limitador(maximo=1, janela=60)
    limitador.permitir("1.1.1.1")
    assert not limitador.permitir("1.1.1.1")
    limitador.limpar("1.1.1.1")
    assert limitador.permitir("1.1.1.1")


def test_esquecer_antigos_liberta_memoria(monkeypatch):
    limitador = protecao.Limitador(maximo=5, janela=10)
    tempo = [1000.0]
    monkeypatch.setattr(protecao.time, "monotonic", lambda: tempo[0])
    for n in range(50):
        limitador.permitir(f"10.0.0.{n}")
    tempo[0] += 20
    limitador.esquecer_antigos()
    assert len(limitador._registos) == 0


@pytest.mark.parametrize(
    "perigoso",
    [
        'evil".pdf\r\nX-Injectado: sim',
        "ficha\nSet-Cookie: roubado=1",
        'a"b"c.pdf',
        "../../etc/passwd",
    ],
)
def test_nome_de_ficheiro_neutraliza_injecao(perigoso):
    seguro = protecao.sanear_nome_ficheiro(perigoso)
    assert "\r" not in seguro
    assert "\n" not in seguro
    assert '"' not in seguro
    assert "/" not in seguro


def test_nome_de_ficheiro_preserva_o_legivel():
    assert protecao.sanear_nome_ficheiro("Sebenta modulo F5.pdf") == (
        "Sebenta modulo F5.pdf"
    )


def test_nome_vazio_tem_alternativa():
    assert protecao.sanear_nome_ficheiro("///") == "documento"


def test_nome_muito_longo_e_cortado():
    assert len(protecao.sanear_nome_ficheiro("a" * 500)) <= 120


def test_endereco_usa_o_cabecalho_do_tunel():
    pedido = _PedidoFalso("127.0.0.1", {"CF-Connecting-IP": "203.0.113.9"})
    assert protecao.endereco_do_pedido(pedido) == "203.0.113.9"


def test_cabecalho_do_tunel_e_ignorado_se_a_ligacao_nao_for_local():
    """Sem isto, qualquer pessoa contornava o limite forjando o cabecalho."""
    pedido = _PedidoFalso("198.51.100.7", {"CF-Connecting-IP": "1.1.1.1"})
    assert protecao.endereco_do_pedido(pedido) == "198.51.100.7"


def test_endereco_sem_cabecalho():
    assert protecao.endereco_do_pedido(_PedidoFalso("127.0.0.1")) == "127.0.0.1"


def test_cabecalhos_de_seguranca_essenciais():
    for chave in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
        "Referrer-Policy",
    ):
        assert chave in protecao.CABECALHOS_SEGURANCA
    assert protecao.CABECALHOS_SEGURANCA["X-Frame-Options"] == "DENY"
