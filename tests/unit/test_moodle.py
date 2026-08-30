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
    for proibido in r'<>:"/\|?*':
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
    html = """
    <div>
      <a href="https://m/pluginfile.php/1/mod_folder/content/0/Ficha%203.pdf">
        Ficha 3 Ficheiro</a>
      <a href="/mod/folder/view.php?id=9">nao e ficheiro</a>
      <a href="https://m/pluginfile.php/1/mod_folder/content/0/Sebenta.pdf">
        Sebenta</a>
    </div>
    """
    encontradas = moodle._ligacoes_de_ficheiro(html)
    assert len(encontradas) == 2
    assert encontradas[0][1] == "Ficha 3"


def test_ligacoes_de_ficheiro_sem_duplicados():
    html = """
    <div>
      <a href="https://m/pluginfile.php/1/a/Ficha.pdf">Ficha</a>
      <a href="https://m/pluginfile.php/1/a/Ficha.pdf">Ficha (icone)</a>
    </div>
    """
    assert len(moodle._ligacoes_de_ficheiro(html)) == 1


def test_ligacoes_encontradas_no_json_embutido():
    """O Moodle recente desenha a arvore de ficheiros por JavaScript: nao ha
    <a> nenhum e os URLs so aparecem no JSON, com as barras escapadas."""
    html = (
        '<div id="folder_tree0"></div><script>'
        'var d = {"children":[{"filename":"Sebenta F5.pdf",'
        '"url":"https:\\/\\/m.pt\\/pluginfile.php\\/1\\/mod_folder'
        '\\/content\\/0\\/Sebenta%20F5.pdf?forcedownload=1"}]};'
        "</script>"
    )
    encontradas = moodle._ligacoes_de_ficheiro(html)
    assert len(encontradas) == 1
    endereco, titulo = encontradas[0]
    assert endereco.startswith("https://m.pt/pluginfile.php/")
    assert "\\" not in endereco
    assert "forcedownload" not in endereco
    assert titulo == "Sebenta F5"


def test_json_embutido_ignorado_quando_ha_ligacoes_normais():
    html = (
        '<a href="https://m/pluginfile.php/1/a/Real.pdf">Real</a>'
        '<script>{"url":"https:\\/\\/m\\/pluginfile.php\\/1\\/a\\/Outro.pdf"}</script>'
    )
    encontradas = moodle._ligacoes_de_ficheiro(html)
    assert [t for _, t in encontradas] == ["Real"]


def test_urls_sem_extensao_sao_descartados_no_json():
    html = '<script>{"url":"https:\\/\\/m\\/pluginfile.php\\/1\\/a\\/sem_extensao"}</script>'
    assert moodle._ligacoes_de_ficheiro(html) == []


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


def test_ficheiros_da_mesma_pasta_tem_origens_distintas(tmp_path):
    """Sem isto, todos os ficheiros de uma pasta partilhavam a origem, logo o
    mesmo id, e so o primeiro sobrevivia a indexacao."""
    relatorio = moodle.RelatorioMoodle()
    origens = {}
    pasta_url = "https://m/mod/folder/view.php?id=42"
    for nome in ("Ficha1.pdf", "Ficha2.pdf", "Ficha3.pdf"):
        moodle._guardar_bytes(
            b"%PDF conteudo", nome, f"folder-42-{nome}",
            f"{pasta_url}#{nome}", nome[:-4],
            tmp_path, origens, relatorio, "Fisica",
        )
    urls = [v["url"] for v in origens.values()]
    assert len(urls) == 3
    assert len(set(urls)) == 3
    assert all(u.startswith(pasta_url) for u in urls)


def _manifesto(pasta, registos):
    import json

    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "_origens.json").write_text(
        json.dumps(registos, ensure_ascii=False), encoding="utf-8"
    )


def test_modulos_conhecidos_lidos_dos_manifestos(tmp_path):
    _manifesto(tmp_path / "TIC", {
        "a.pdf": {"url": "https://m.pt/mod/resource/view.php?id=101", "titulo": "A"},
        "b.pdf": {"url": "https://m.pt/mod/folder/view.php?id=202#b.pdf", "titulo": "B"},
    })
    _manifesto(tmp_path / "Fisica", {
        "c.pdf": {"url": "https://m.pt/mod/resource/view.php?id=303", "titulo": "C"},
    })
    assert moodle.modulos_com_ficheiros(tmp_path) == {101, 202, 303}


def test_modulos_conhecidos_aceita_manifesto_antigo(tmp_path):
    """O formato antigo guardava o url como string, nao como dicionario."""
    _manifesto(tmp_path / "Escola", {
        "p.html": "https://m.pt/mod/page/view.php?id=404",
    })
    assert moodle.modulos_com_ficheiros(tmp_path) == {404}


def test_modulos_conhecidos_ignora_manifesto_corrompido(tmp_path):
    pasta = tmp_path / "TIC"
    pasta.mkdir(parents=True)
    (pasta / "_origens.json").write_text("{quebrado", encoding="utf-8")
    _manifesto(tmp_path / "Fisica", {
        "c.pdf": {"url": "https://m.pt/mod/resource/view.php?id=7", "titulo": "C"},
    })
    assert moodle.modulos_com_ficheiros(tmp_path) == {7}


def test_sem_manifestos_nada_e_conhecido(tmp_path):
    assert moodle.modulos_com_ficheiros(tmp_path) == set()


def test_modulo_novo_constroi_o_url():
    novo = moodle.ModuloNovo("TIC", "resource", 55, "Ficha 3")
    assert novo.url == "/mod/resource/view.php?id=55"


def test_filtrar_disciplinas_por_nome():
    todas = [(1, "PSI9-Matemática"), (2, "PSI9-Português")]
    assert moodle._filtrar_disciplinas(todas, ["matem"]) == [(1, "PSI9-Matemática")]
    assert moodle._filtrar_disciplinas(todas, None) == todas


def test_verificar_devolve_so_o_que_falta(tmp_path, monkeypatch):
    """A deteccao compara o que o Moodle anuncia com o que ja esta ca."""
    _manifesto(tmp_path / "TIC", {
        "a.pdf": {"url": "https://m.pt/mod/resource/view.php?id=101", "titulo": "A"},
    })

    monkeypatch.setattr(
        moodle, "configuracao", lambda: ("https://m.pt", "aluno", "x")
    )
    monkeypatch.setattr(moodle, "iniciar_sessao", lambda *a: object())
    monkeypatch.setattr(
        moodle, "listar_disciplinas", lambda *a: [(9, "PSI9-TIC")]
    )
    monkeypatch.setattr(
        moodle,
        "pagina_da_disciplina",
        lambda *a: ("PSI9-TIC", [
            ("resource", 101, "Ja ca esta"),
            ("resource", 999, "Ficha nova"),
        ]),
    )

    novos, vistos = moodle.verificar(tmp_path, intervalo=0)
    assert vistos == 2
    assert [n.identificador for n in novos] == [999]
    assert novos[0].titulo == "Ficha nova"
    assert novos[0].disciplina == "TIC"


def test_verificar_sem_novidades(tmp_path, monkeypatch):
    _manifesto(tmp_path / "TIC", {
        "a.pdf": {"url": "https://m.pt/mod/resource/view.php?id=101", "titulo": "A"},
    })
    monkeypatch.setattr(
        moodle, "configuracao", lambda: ("https://m.pt", "aluno", "x")
    )
    monkeypatch.setattr(moodle, "iniciar_sessao", lambda *a: object())
    monkeypatch.setattr(
        moodle, "listar_disciplinas", lambda *a: [(9, "PSI9-TIC")]
    )
    monkeypatch.setattr(
        moodle,
        "pagina_da_disciplina",
        lambda *a: ("PSI9-TIC", [("resource", 101, "Ja ca esta")]),
    )
    novos, vistos = moodle.verificar(tmp_path, intervalo=0)
    assert novos == []
    assert vistos == 1


def test_vistos_contam_como_conhecidos(tmp_path):
    """Um modulo esteril fica marcado, para nao ser anunciado todos os dias."""
    assert moodle.modulos_vistos(tmp_path) == set()
    moodle.marcar_vistos(tmp_path, {500, 501})
    assert moodle.modulos_vistos(tmp_path) == {500, 501}
    # nao produziram ficheiro, logo nao estao nos manifestos
    assert moodle.modulos_com_ficheiros(tmp_path) == set()
    # mas contam como conhecidos, e e isso que a deteccao usa
    assert moodle.modulos_conhecidos(tmp_path) == {500, 501}


def test_marcar_vistos_acumula(tmp_path):
    moodle.marcar_vistos(tmp_path, {1})
    moodle.marcar_vistos(tmp_path, {2})
    assert moodle.modulos_vistos(tmp_path) == {1, 2}


def test_marcar_vistos_guarda_a_data(tmp_path):
    import json
    from datetime import date

    moodle.marcar_vistos(tmp_path, {7})
    registo = json.loads((tmp_path / moodle.NOME_VISTOS).read_text(encoding="utf-8"))
    assert registo["7"] == date.today().isoformat()


def test_vistos_corrompido_nao_derruba(tmp_path):
    (tmp_path / moodle.NOME_VISTOS).write_text("{partido", encoding="utf-8")
    assert moodle.modulos_vistos(tmp_path) == set()


def test_marcar_vistos_vazio_nao_cria_ficheiro(tmp_path):
    moodle.marcar_vistos(tmp_path, set())
    assert not (tmp_path / moodle.NOME_VISTOS).exists()


def test_verificar_ignora_modulo_ja_examinado(tmp_path, monkeypatch):
    """O modulo esteril nao volta a ser anunciado depois de marcado."""
    moodle.marcar_vistos(tmp_path, {999})

    monkeypatch.setattr(
        moodle, "configuracao", lambda: ("https://m.pt", "aluno", "x")
    )
    monkeypatch.setattr(moodle, "iniciar_sessao", lambda *a: object())
    monkeypatch.setattr(
        moodle, "listar_disciplinas", lambda *a: [(9, "PSI9-TIC")]
    )
    monkeypatch.setattr(
        moodle,
        "pagina_da_disciplina",
        lambda *a: ("PSI9-TIC", [("folder", 999, "Pasta vazia")]),
    )
    novos, vistos = moodle.verificar(tmp_path, intervalo=0)
    assert novos == []
    assert vistos == 1


def test_filtro_de_disciplina_ignora_acentos():
    """"--disciplina portugues" devolvia zero por causa do cedilha."""
    todas = [(1, "PSI9-Português"), (2, "PSI9-Matemática")]
    assert moodle._filtrar_disciplinas(todas, ["portugues"]) == [(1, "PSI9-Português")]
    assert moodle._filtrar_disciplinas(todas, ["matematica"]) == [(2, "PSI9-Matemática")]


def test_filtro_aceita_abreviatura():
    todas = [(1, "PSI9-Português")]
    assert moodle._filtrar_disciplinas(todas, ["portug"]) == todas


def test_filtro_nao_casa_pedaco_no_meio_de_palavra():
    """"tic" estava a apanhar "matematica" e a sincronizar a disciplina errada."""
    todas = [(1, "PSI9-Matemática"), (2, "TIC")]
    assert moodle._filtrar_disciplinas(todas, ["tic"]) == [(2, "TIC")]


def test_data_da_resposta_le_o_last_modified():
    class Resposta:
        headers = {"Last-Modified": "Mon, 20 Oct 2025 17:21:05 GMT"}

    assert moodle.data_da_resposta(Resposta()) == "2025-10-20"


def test_sem_last_modified_nao_inventa_data():
    class Resposta:
        headers = {}

    assert moodle.data_da_resposta(Resposta()) == ""


def test_data_invalida_nao_rebenta():
    class Resposta:
        headers = {"Last-Modified": "ontem a tarde"}

    assert moodle.data_da_resposta(Resposta()) == ""
