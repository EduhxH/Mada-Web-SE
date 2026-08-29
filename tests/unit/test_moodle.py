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


def test_pasta_vazia_quando_nao_sobra_nada():
    """Devolve "" para quem chama poder usar o nome da lista em vez disso."""
    assert moodle.pasta_da_disciplina("...") == ""
    assert moodle.pasta_da_disciplina("Disciplina de .....") == ""


def test_prefixos_encadeados_sao_todos_removidos():
    assert moodle.pasta_da_disciplina(
        "Disciplina: PSI9-Arquitetura de Computadores"
    ) == "Arquitetura de Computadores"
    assert moodle.pasta_da_disciplina("Disciplina: Turma PSI9") == "Turma PSI9"


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


def test_titulo_perde_o_rotulo_de_tipo():
    assert moodle._limpar_titulo("Sebenta modulo F5 Ficheiro") == "Sebenta modulo F5"
    assert moodle._limpar_titulo("Guioes e Fichas Pasta") == "Guioes e Fichas"
    assert moodle._limpar_titulo("Manual Arrays") == "Manual Arrays"


def test_modulo_url_ficou_de_fora():
    """Aponta para sites externos e dava a maioria dos 404."""
    assert "url" not in moodle.MODULOS_UTEIS


def test_so_apanha_ligacoes_da_regiao_de_conteudo():
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <div id="block-region-side">
        <a href="/mod/page/view.php?id=1">Anuncio do bloco lateral</a>
      </div>
      <div id="region-main">
        <a href="/mod/resource/view.php?id=2">Sebenta Ficheiro</a>
      </div>
    </body></html>
    """

    class Falsa:
        text = html
        status_code = 200

    class SessaoFalsa:
        def get(self, *a, **k):
            return Falsa()

    _, recursos = moodle.pagina_da_disciplina(SessaoFalsa(), "https://x", 1)
    identificadores = [r[1] for r in recursos]
    assert 2 in identificadores
    assert 1 not in identificadores


def test_ligacoes_de_ficheiro_apanha_pluginfile():
    from bs4 import BeautifulSoup

    html = """
    <div>
      <a href="https://m/pluginfile.php/1/mod_folder/content/0/Ficha%203.pdf">
        Ficha 3 Ficheiro</a>
      <a href="/mod/folder/view.php?id=9">nao e ficheiro</a>
      <a href="https://m/pluginfile.php/1/mod_folder/content/0/Sebenta.pdf">
        Sebenta</a>
    </div>
    """
    encontradas = moodle._ligacoes_de_ficheiro(BeautifulSoup(html, "html.parser"))
    assert len(encontradas) == 2
    assert encontradas[0][1] == "Ficha 3"


def test_ligacoes_de_ficheiro_sem_duplicados():
    from bs4 import BeautifulSoup

    html = """
    <div>
      <a href="https://m/pluginfile.php/1/a/Ficha.pdf">Ficha</a>
      <a href="https://m/pluginfile.php/1/a/Ficha.pdf">Ficha (icone)</a>
    </div>
    """
    assert len(moodle._ligacoes_de_ficheiro(BeautifulSoup(html, "html.parser"))) == 1


def test_nome_guardado_e_estavel_entre_execucoes():
    """A chave nao inclui sesskey: o mesmo ficheiro nao pode mudar de nome,
    senao aparece duas vezes no indice."""
    from app.crawler.web_source import nome_ficheiro

    chave = "folder-82160-Sebenta modulo F5.pdf"
    assert nome_ficheiro(chave, ".pdf") == nome_ficheiro(chave, ".pdf")


def test_extensao_recusada_nao_e_guardada(tmp_path):
    relatorio = moodle.RelatorioMoodle()
    origens = {}
    guardou = moodle._guardar_bytes(
        b"dados", "folha.xlsx", "chave", "https://m/x", "Folha",
        tmp_path, origens, relatorio, "Fisica",
    )
    assert guardou is False
    assert origens == {}
    assert relatorio.ficheiros == 0


def test_ficheiro_aceite_entra_no_manifesto(tmp_path):
    relatorio = moodle.RelatorioMoodle()
    origens = {}
    assert moodle._guardar_bytes(
        b"%PDF-1.4 conteudo", "Sebenta.pdf", "folder-1-Sebenta.pdf",
        "https://m/mod/folder/view.php?id=1", "Sebenta F5",
        tmp_path, origens, relatorio, "Fisica",
    )
    (guardado,) = origens
    assert origens[guardado]["titulo"] == "Sebenta F5"
    assert (tmp_path / guardado).read_bytes().startswith(b"%PDF")
    assert relatorio.disciplinas["Fisica"] == 1
