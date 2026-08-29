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
