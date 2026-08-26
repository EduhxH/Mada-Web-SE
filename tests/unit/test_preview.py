from app.interface.preview import descrever, fragmento, resolver_origem
from app.models.document import Documento


def _doc(origem, disciplina="Matematica"):
    return Documento(1, "Ficha 3", "algoritmos e ciclos de estudo", origem, disciplina)


def test_resolve_ficheiro_solto_com_pagina():
    caminho, interno, pagina, rotulo = resolver_origem(
        "data/raw/psi9/Horarios/horarios.pdf#pagina=12"
    )
    assert caminho.name == "horarios.pdf"
    assert interno is None
    assert pagina == 12
    assert rotulo == "pagina"


def test_resolve_ficheiro_dentro_de_zip():
    caminho, interno, pagina, _ = resolver_origem(
        "data/raw/psi9/Fisica/Sebenta.zip!modulo/F5.pdf#pagina=2"
    )
    assert caminho.name == "Sebenta.zip"
    assert interno == "modulo/F5.pdf"
    assert pagina == 2


def test_resolve_slide():
    _, _, pagina, rotulo = resolver_origem("x/apresentacao.pptx#slide=4")
    assert (pagina, rotulo) == (4, "slide")


def test_resolve_sem_pagina():
    caminho, interno, pagina, rotulo = resolver_origem("x/notas.txt")
    assert (caminho.name, interno, pagina, rotulo) == ("notas.txt", None, None, "")


def test_descreve_ficheiro_solto():
    dados = descrever(_doc("data/raw/psi9/Horarios/horarios.pdf#pagina=12"))
    assert dados["ficheiro"] == "horarios.pdf"
    assert dados["tipo"] == "PDF"
    assert dados["local"] == "pagina 12"
    assert dados["disciplina"] == "Matematica"
    assert "dentro_de" not in dados


def test_descreve_ficheiro_em_zip():
    dados = descrever(_doc("data/raw/psi9/F/Sebenta.zip!F5.pdf#pagina=2"))
    assert dados["ficheiro"] == "F5.pdf"
    assert dados["dentro_de"] == "Sebenta.zip"


def test_conta_palavras():
    dados = descrever(_doc("x/a.pdf"))
    assert dados["palavras"] == "5 palavras"


def test_fragmento_tem_metadados_e_destaque():
    saida = fragmento(_doc("data/raw/psi9/M/ficha.pdf#pagina=3"), "algoritmos")
    assert "PDF" in saida
    assert "pagina 3" in saida
    assert "Matematica" in saida
    assert "ficha.pdf" in saida
    assert "<b>algoritmos</b>" in saida


def test_fragmento_escapa_html():
    doc = Documento(1, "T", "<script>alerta</script> perigoso", "x/a.pdf", "X")
    saida = fragmento(doc, "perigoso")
    assert "<script>" not in saida
    assert "&lt;script&gt;" in saida


def test_fragmento_com_consulta_vazia_nao_rebenta():
    saida = fragmento(_doc("x/a.pdf"), "")
    assert "PDF" in saida


def test_descreve_pagina_web():
    doc = Documento(
        1, "Regulamento", "texto da pagina", "https://www.sefo.pt/regulamento", "Escola"
    )
    dados = descrever(doc)
    assert dados["tipo"] == "pagina web"
    assert dados["ficheiro"] == "https://www.sefo.pt/regulamento"
    assert "local" not in dados
