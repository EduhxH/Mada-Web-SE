import pytest

from app.crawler import moodle


def test_configuracao_falha_sem_credenciais(monkeypatch, tmp_path):
    monkeypatch.setattr(moodle, "carregar_env", lambda: None)
    for var in (moodle.VAR_URL, moodle.VAR_UTILIZADOR, moodle.VAR_SENHA):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(moodle.ErroMoodle) as erro:
        moodle.configuracao()
    assert ".env" in str(erro.value)
    # a mensagem nunca deve conter uma senha
    assert "senha=" not in str(erro.value).lower().replace("_senha=a_sua", "")


def test_configuracao_le_do_ambiente(monkeypatch):
    monkeypatch.setattr(moodle, "carregar_env", lambda: None)
    monkeypatch.setenv(moodle.VAR_URL, "https://moodle.exemplo.pt/")
    monkeypatch.setenv(moodle.VAR_UTILIZADOR, "aluno")
    monkeypatch.setenv(moodle.VAR_SENHA, "x")
    url, utilizador, _ = moodle.configuracao()
    assert url == "https://moodle.exemplo.pt"  # barra final removida
    assert utilizador == "aluno"


def test_pasta_da_disciplina_limpa_prefixos():
    assert moodle._pasta_da_disciplina("PSI9-Matemática") == "Matemática"
    assert moodle._pasta_da_disciplina("Disciplina de Português") == "Português"
    assert moodle._pasta_da_disciplina("PSI9: Física-Química") == "Física-Química"


def test_pasta_da_disciplina_remove_caracteres_invalidos():
    resultado = moodle._pasta_da_disciplina('Mat/emat*ica?')
    for proibido in '<>:"/\|?*':
        assert proibido not in resultado


def test_nome_da_resposta_usa_content_disposition():
    class Falsa:
        headers = {"Content-Disposition": 'attachment; filename="Ficha 3.pdf"'}
        url = "https://x/mod/resource/view.php?id=9"

    assert moodle._nome_da_resposta(Falsa(), "alt.bin") == "Ficha 3.pdf"


def test_nome_da_resposta_cai_no_url():
    class Falsa:
        headers = {}
        url = "https://x/pluginfile.php/1/mod_resource/content/0/sebenta.pdf"

    assert moodle._nome_da_resposta(Falsa(), "alt.bin") == "sebenta.pdf"


def test_nome_da_resposta_usa_a_alternativa():
    class Falsa:
        headers = {}
        url = "https://x/mod/resource/view.php?id=9"

    assert moodle._nome_da_resposta(Falsa(), "alt.bin") == "alt.bin"


def test_modulos_de_conversa_ficam_de_fora():
    for modulo in ("forum", "quiz", "chat", "assign"):
        assert modulo not in moodle.MODULOS_UTEIS


def test_pasta_nunca_termina_em_ponto():
    """O Windows recusa pastas terminadas em ponto: era o FileNotFoundError."""
    for nome in ("PSI9-Arquitetura de Computa...", "Algo.", "Outro . . ."):
        resultado = moodle.pasta_da_disciplina(nome)
        assert not resultado.endswith(".")
        assert not resultado.endswith(" ")


def test_pasta_remove_reticencias_unicode():
    assert "\u2026" not in moodle.pasta_da_disciplina("Tecnologias de Informa\u2026")


def test_pasta_nunca_fica_vazia():
    assert moodle.pasta_da_disciplina("...") == "disciplina"
    assert moodle.pasta_da_disciplina("///") != ""


def test_sesskey_extraido_do_javascript():
    class Falsa:
        text = 'var M = {"sesskey":"aBc123XyZ","other":1};'
        status_code = 200

    class SessaoFalsa:
        def get(self, *a, **k):
            return Falsa()

    assert moodle.obter_sesskey(SessaoFalsa(), "https://x") == "aBc123XyZ"


def test_sesskey_extraido_de_um_link():
    class Falsa:
        text = '<a href="/login/logout.php?sesskey=Zx9Qw">Sair</a>'
        status_code = 200

    class SessaoFalsa:
        def get(self, *a, **k):
            return Falsa()

    assert moodle.obter_sesskey(SessaoFalsa(), "https://x") == "Zx9Qw"


def test_sesskey_ausente_devolve_vazio():
    class Falsa:
        text = "<html>sem nada</html>"
        status_code = 200

    class SessaoFalsa:
        def get(self, *a, **k):
            return Falsa()

    assert moodle.obter_sesskey(SessaoFalsa(), "https://x") == ""


def test_paginas_do_moodle_sao_guardadas_como_html():
    assert "page" in moodle.MODULOS_HTML
    assert "book" in moodle.MODULOS_HTML
    assert "resource" not in moodle.MODULOS_HTML
