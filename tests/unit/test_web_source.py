from app.crawler.local_source import carregar, origem_declarada, titulo_html
from app.crawler.web_source import (
    _e_pagina,
    _extrair_ligacoes,
    _guardar,
    nome_ficheiro,
    normalizar,
)

PAGINA = """<html><head><title>Regulamento Interno</title></head>
<body>
<nav>menu que nao deve ser indexado</nav>
<h1>Regulamento</h1>
<p>As faltas devem ser justificadas em cinco dias uteis.</p>
<script>var lixo = 1;</script>
<a href="/a-esco/faq">FAQ</a>
<a href="https://www.sefo.pt/noticias">Noticias</a>
<a href="https://facebook.com/outra">Externo</a>
<a href="/imagem.png">Imagem</a>
<footer>rodape</footer>
</body></html>"""


def test_normalizar_remove_barra_e_fragmento():
    assert normalizar("https://x.pt/a/") == "https://x.pt/a"
    assert normalizar("https://x.pt/a#seccao") == "https://x.pt/a"
    assert normalizar("https://x.pt/") == "https://x.pt/"


def test_normalizar_preserva_query():
    assert normalizar("https://x.pt/a?p=2") == "https://x.pt/a?p=2"


def test_nome_ficheiro_e_unico_e_legivel():
    a = nome_ficheiro("https://www.sefo.pt/a-esco/regulamentos")
    b = nome_ficheiro("https://www.sefo.pt/a-esco/outra")
    assert a.startswith("a-esco-regulamentos-")
    assert a.endswith(".html")
    assert a != b


def test_nome_ficheiro_da_raiz():
    assert nome_ficheiro("https://www.sefo.pt/").startswith("index-")


def test_recursos_nao_sao_paginas():
    assert _e_pagina("https://x.pt/a/pagina")
    assert not _e_pagina("https://x.pt/estilo.css")
    assert not _e_pagina("https://x.pt/foto.JPG")


def test_extrair_ligacoes_filtra_dominio_e_recursos():
    ligacoes = _extrair_ligacoes(PAGINA, "https://www.sefo.pt/x", "www.sefo.pt")
    assert "https://www.sefo.pt/a-esco/faq" in ligacoes
    assert "https://www.sefo.pt/noticias" in ligacoes
    assert not any("facebook" in u for u in ligacoes)
    assert not any(".png" in u for u in ligacoes)


def test_guardar_injecta_a_url_de_origem(tmp_path):
    url = "https://www.sefo.pt/a-esco/regulamentos"
    _guardar(tmp_path, url, PAGINA)
    guardado = (tmp_path / nome_ficheiro(url)).read_bytes()
    assert origem_declarada(guardado) == url
    assert titulo_html(guardado) == "Regulamento Interno"


def test_pagina_guardada_vira_documento_com_url_e_titulo(tmp_path):
    pasta = tmp_path / "Escola"
    pasta.mkdir()
    url = "https://www.sefo.pt/a-esco/regulamentos"
    _guardar(pasta, url, PAGINA)

    documentos, _ = carregar(tmp_path)
    assert len(documentos) == 1
    doc = documentos[0]
    assert doc.origem == url
    assert doc.titulo == "Regulamento Interno"
    assert doc.disciplina == "Escola"
    assert "faltas devem ser justificadas" in doc.texto
    assert "menu que nao deve ser indexado" not in doc.texto
    assert "var lixo" not in doc.texto
    assert "rodape" not in doc.texto


def test_nome_ficheiro_para_pdf():
    nome = nome_ficheiro("https://www.sefo.pt/wp-content/uploads/Regulamento.pdf", ".pdf")
    assert nome.startswith("wp-content-uploads-Regulamento-")
    assert nome.endswith(".pdf")
    assert ".pdf.pdf" not in nome


def test_manifesto_da_a_url_como_origem(tmp_path):
    import json

    pasta = tmp_path / "Escola"
    pasta.mkdir()
    (pasta / "doc-abc123.pdf").write_bytes(b"nao e um pdf valido")
    (pasta / "aula.txt").write_text("conteudo sobre algoritmos", encoding="utf-8")
    (pasta / "_origens.json").write_text(
        json.dumps({"aula.txt": "https://www.sefo.pt/aula"}), encoding="utf-8"
    )

    documentos, _ = carregar(tmp_path)
    origens = {d.origem for d in documentos}
    assert "https://www.sefo.pt/aula" in origens


def test_manifesto_nao_e_indexado(tmp_path):
    import json

    pasta = tmp_path / "Escola"
    pasta.mkdir()
    (pasta / "_origens.json").write_text(json.dumps({"x": "y"}), encoding="utf-8")
    documentos, _ = carregar(tmp_path)
    assert documentos == []


def test_manifesto_invalido_nao_derruba_a_carga(tmp_path):
    pasta = tmp_path / "Escola"
    pasta.mkdir()
    (pasta / "_origens.json").write_text("{isto nao e json", encoding="utf-8")
    (pasta / "aula.txt").write_text("conteudo sobre algoritmos", encoding="utf-8")
    documentos, _ = carregar(tmp_path)
    assert len(documentos) == 1
    assert documentos[0].origem.endswith("aula.txt")
