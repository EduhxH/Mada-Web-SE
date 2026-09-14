"""A barreira de sessao do servidor, sem levantar servidor nenhum.

`_participante` so toca em `self.headers`, portanto testa-se com um objeto que
tem cabecalhos e mais nada. O que isto guarda e uma linha: se alguem trocar
`participante_da_sessao` de volta por `validar_sessao`, os testes do `auth`
continuam todos verdes e um codigo revogado volta a entrar durante trinta dias.
"""

from app.interface import auth, web


class Pedido:
    """Faz de pedido HTTP: para `_participante` um pedido e um dicionario."""

    def __init__(self, cookie: str | None = None) -> None:
        self.headers = {"Cookie": cookie} if cookie else {}


def _ler(pedido):
    return web._Manipulador._participante(pedido)


def _isolar(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CAMINHO_PARTICIPANTES", tmp_path / "p.json")
    monkeypatch.setattr(auth, "CAMINHO_SEGREDO", tmp_path / "s.txt")
    # As epocas de sessao tambem. Sem isto os testes escreviam no ficheiro real,
    # e correr a bateria com o servidor no ar expulsava a turma inteira.
    monkeypatch.setattr(auth, "CAMINHO_CORTES", tmp_path / "cortes.json")
    monkeypatch.setattr(auth, "_cache_epocas", None)
    monkeypatch.setattr(auth, "CAMINHO_ENV", tmp_path / "nao-existe.env")
    monkeypatch.setattr(auth, "_env_carregado", True)
    monkeypatch.setattr(auth, "_cache_rotulos", None)
    monkeypatch.delenv(auth.VAR_SEGREDO, raising=False)


def test_sem_cookie_ninguem_entra(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert _ler(Pedido()) is None


def test_cookie_valido_entra(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(2)
    cookie = auth.criar_sessao("aluno-01", auth.segredo())
    assert _ler(Pedido(f"{auth.NOME_COOKIE}={cookie}")) == "aluno-01"


def test_cookie_de_rotulo_revogado_nao_entra(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(2)
    cookie = auth.criar_sessao("aluno-01", auth.segredo())
    auth.revogar("aluno-01")
    assert _ler(Pedido(f"{auth.NOME_COOKIE}={cookie}")) is None


def test_cookie_assinado_com_outra_chave_nao_entra(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    forjado = auth.criar_sessao("aluno-01", b"nao-e-o-segredo-desta-maquina")
    assert _ler(Pedido(f"{auth.NOME_COOKIE}={forjado}")) is None


def test_cookie_com_lixo_nao_rebenta(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    for valor in ("lixo", "=", "a|b|c|d", f"{auth.NOME_COOKIE}=", "\x00"):
        assert _ler(Pedido(valor)) is None
