"""Ficheiros carregados: o analisador multipart, o portao de leitura, os limites."""

import pytest

from app.interface import media

CRLF = bytes.fromhex("0d0a")
FRONTEIRA = b"----MadalenaTeste"

PNG = bytes.fromhex("89504e470d0a1a0a") + b"resto do ficheiro"
JPEG = bytes.fromhex("ffd8ff") + b"resto"
GIF = b"GIF89a" + b"resto"
WEBP = b"RIFF" + b"1234" + b"WEBP" + b"resto"
MP4 = b"0000" + b"ftyp" + b"isom" + b"resto"
WEBM = bytes.fromhex("1a45dfa3") + b"resto"


def _parte(cabecalhos: bytes, dados: bytes) -> bytes:
    return b"--" + FRONTEIRA + CRLF + cabecalhos + CRLF + CRLF + dados + CRLF


def _corpo(*partes: bytes) -> bytes:
    return b"".join(partes) + b"--" + FRONTEIRA + b"--" + CRLF


def _tipo() -> str:
    return f"multipart/form-data; boundary={FRONTEIRA.decode()}"


def _campo(nome: str, valor: bytes) -> bytes:
    return _parte(
        f'Content-Disposition: form-data; name="{nome}"'.encode(), valor
    )


def _ficheiro(nome: str, nome_ficheiro: str, dados: bytes) -> bytes:
    return _parte(
        f'Content-Disposition: form-data; name="{nome}";'
        f' filename="{nome_ficheiro}"'.encode()
        + CRLF
        + b"Content-Type: application/octet-stream",
        dados,
    )


def _isolar(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "PASTA", tmp_path / "media")
    monkeypatch.setattr(media, "PASTA_PERFIL", tmp_path / "perfil")


# ------------------------------------------------------------- multipart


def test_reparte_campos_e_ficheiros():
    corpo = _corpo(
        _campo("titulo", "Acentuação à solta".encode("utf-8")),
        _campo("corpo", b"linha 1\nlinha 2"),
        _ficheiro("media", "a foto.PNG", PNG),
    )
    campos, ficheiros = media.analisar_multipart(corpo, _tipo())
    assert campos == {"titulo": "Acentuação à solta", "corpo": "linha 1\nlinha 2"}
    assert len(ficheiros) == 1
    assert ficheiros[0].campo == "media"
    assert ficheiros[0].extensao == "png"


def test_os_bytes_do_ficheiro_chegam_intactos():
    """O CRLF antes do delimitador pertence a sintaxe, nao ao ficheiro.

    Sem o tirar, cada imagem guardada ficava dois bytes maior do que a original
    - o suficiente para um PNG deixar de abrir.
    """
    dados = bytes(range(256)) * 4
    corpo = _corpo(_ficheiro("media", "x.png", dados))
    _, ficheiros = media.analisar_multipart(corpo, _tipo())
    assert ficheiros[0].dados == dados


def test_campo_de_ficheiro_vazio_nao_vira_campo_de_texto():
    """Um <input type=file> nao escolhido manda `filename=""`."""
    corpo = _corpo(_campo("titulo", b"Post"), _ficheiro("media", "", b""))
    campos, ficheiros = media.analisar_multipart(corpo, _tipo())
    assert campos == {"titulo": "Post"}
    assert ficheiros == []


@pytest.mark.parametrize(
    "corpo,tipo",
    [
        (b"", "multipart/form-data; boundary=x"),
        (b"lixo sem estrutura", "multipart/form-data; boundary=x"),
        (b"--x" + CRLF + b"sem linha em branco", "multipart/form-data; boundary=x"),
        (b"qualquer coisa", "application/x-www-form-urlencoded"),
        (b"qualquer coisa", ""),
        (bytes(range(256)), "multipart/form-data; boundary=x"),
    ],
)
def test_entrada_estragada_nao_levanta(corpo, tipo):
    campos, ficheiros = media.analisar_multipart(corpo, tipo)
    assert isinstance(campos, dict) and isinstance(ficheiros, list)


def test_varios_ficheiros_no_mesmo_corpo():
    corpo = _corpo(
        _ficheiro("media", "a.png", PNG), _ficheiro("outro", "b.gif", GIF)
    )
    _, ficheiros = media.analisar_multipart(corpo, _tipo())
    assert [f.campo for f in ficheiros] == ["media", "outro"]


# -------------------------------------------------------------- validacao


@pytest.mark.parametrize(
    "nome,dados",
    [("a.png", PNG), ("a.jpg", JPEG), ("a.jpeg", JPEG), ("a.gif", GIF),
     ("a.webp", WEBP), ("a.mp4", MP4), ("a.webm", WEBM)],
)
def test_formatos_aceites(nome, dados):
    assert media.validar(media.Carregado("m", nome, dados)) == ""


def test_a_extensao_tem_de_concordar_com_os_bytes():
    """Servir como image/png o que nao e um PNG e uma promessa falsa ao browser."""
    motivo = media.validar(media.Carregado("m", "x.png", b"<html>ola</html>"))
    assert "não é um png de verdade" in motivo


def test_png_com_bytes_de_gif_e_recusado():
    assert media.validar(media.Carregado("m", "x.png", GIF)) != ""


@pytest.mark.parametrize("nome", ["x.svg", "x.exe", "x.html", "x.php", "x", "x."])
def test_formatos_recusados(nome):
    """O SVG e o unico formato de imagem que e um documento com script dentro."""
    motivo = media.validar(media.Carregado("m", nome, PNG))
    assert "formato não aceito" in motivo


def test_limite_de_tamanho():
    gordo = media.Carregado("m", "x.png", PNG + b"0" * (7 * 1024 * 1024))
    assert "demasiado" in media.validar(gordo)


def test_video_tem_limite_maior_que_imagem():
    assert media.limites()["mp4"] > media.limites()["png"]


# ------------------------------------------------------ guardar e ler


def test_guardar_da_nome_de_resumo_e_le_de_volta(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    nome, erro = media.guardar(media.Carregado("m", "a minha foto.png", PNG))
    assert erro == ""
    assert nome.endswith(".png") and len(nome) == 20
    assert media.ler(nome) == (PNG, "image/png")


def test_o_mesmo_ficheiro_duas_vezes_nao_duplica(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    um, _ = media.guardar(media.Carregado("m", "a.png", PNG))
    dois, _ = media.guardar(media.Carregado("m", "outro nome.png", PNG))
    assert um == dois
    assert len(media.listar()) == 1


def test_o_nome_de_quem_carrega_e_ignorado(tmp_path, monkeypatch):
    """Nao ha caminho escolhido de fora, portanto nao ha travessia a tentar."""
    _isolar(tmp_path, monkeypatch)
    nome, erro = media.guardar(
        media.Carregado("m", "../../../.ssh/authorized_keys.png", PNG)
    )
    assert erro == ""
    assert "/" not in nome and ".." not in nome


@pytest.mark.parametrize(
    "nome",
    ["../../.env", "a/b.png", "a" + chr(92) + "b.png", "..png", ".png", "x.",
     "x.svg", "a.b.png", "", "x.png.exe"],
)
def test_portao_de_leitura_recusa(nome, tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert media.ler(nome) == (b"", "")


def test_apagar(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    nome, _ = media.guardar(media.Carregado("m", "a.png", PNG))
    assert media.apagar(nome) is True
    assert media.ler(nome) == (b"", "")
    assert media.apagar(nome) is False
    assert media.apagar("../../.env") is False


def test_listar_do_mais_recente_para_o_mais_antigo(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    media.guardar(media.Carregado("m", "a.png", PNG))
    media.guardar(media.Carregado("m", "b.gif", GIF))
    listados = media.listar()
    assert len(listados) == 2
    assert listados[0]["quando"] >= listados[1]["quando"]
    assert {i["familia"] for i in listados} == {media.IMAGEM}


def test_marcacao_de_video_e_de_imagem():
    assert media.marcacao_de("a.png") == "![](/media/a.png)"
    assert media.marcacao_de("a.mp4") == "!video(/media/a.mp4)"


# ------------------------------------------------------------------ perfil


def test_perfil_substitui_a_foto_anterior(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    media.guardar_perfil("admin-01", media.Carregado("f", "a.png", PNG))
    assert media.perfil_de("admin-01") == "admin-01.png"
    media.guardar_perfil("admin-01", media.Carregado("f", "b.gif", GIF))
    assert media.perfil_de("admin-01") == "admin-01.gif"
    assert not (tmp_path / "perfil" / "admin-01.png").exists()


def test_perfil_nao_aceita_video(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    _, erro = media.guardar_perfil("admin-01", media.Carregado("f", "a.mp4", MP4))
    assert "formato não aceito" in erro


def test_rotulo_estranho_nao_escreve_fora_da_pasta(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    nome, erro = media.guardar_perfil(
        "../../.env", media.Carregado("f", "a.png", PNG)
    )
    assert erro == "" and nome == "env.png"
    assert (tmp_path / "perfil" / "env.png").exists()


def test_perfil_de_quem_nao_tem(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert media.perfil_de("aluno-07") == ""
    assert media.perfil_de("") == ""


def test_legivel():
    assert media.legivel(500) == "500 B"
    assert media.legivel(2048) == "2 KB"
    assert media.legivel(3 * 1024 * 1024) == "3.0 MB"
