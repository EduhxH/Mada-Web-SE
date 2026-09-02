"""A pagina montada: o que se ve, e o que nao se deve ver duas vezes."""

from app.interface import paginacao, web
from app.models.document import Documento


def _docs(quantos, disciplina="Escola"):
    return [
        (
            Documento(
                i,
                f"Documento {i}",
                "texto com palavras suficientes para um trecho",
                "https://moodle.sefo.pt/x",
                disciplina,
            ),
            1.0 - i / 1000,
        )
        for i in range(1, quantos + 1)
    ]


def test_corpo_mostra_so_a_janela_pedida():
    documentos = _docs(57)
    janela = paginacao.calcular(57, 3)
    corpo = web._corpo_resultados(
        documentos, "q", "", {"texto"}, "", janela=janela
    )
    assert corpo.count('class="resultado"') == 10
    assert "Documento 21" in corpo
    assert "Documento 30" in corpo
    assert "Documento 20" not in corpo
    assert "Documento 31" not in corpo


def test_ultima_pagina_mostra_o_que_sobra():
    documentos = _docs(57)
    janela = paginacao.calcular(57, 6)
    corpo = web._corpo_resultados(documentos, "q", "", {"texto"}, "", janela=janela)
    assert corpo.count('class="resultado"') == 7


def test_posicao_continua_a_contar_entre_paginas():
    """A posicao vai no registo de cliques: na pagina 3 o 1o e o 21o."""
    janela = paginacao.calcular(57, 3)
    corpo = web._corpo_resultados(_docs(57), "q", "", {"texto"}, "", janela=janela)
    assert "p=21" in corpo
    assert "p=1&" not in corpo


def test_barra_de_paginas_marca_a_atual_e_nao_a_liga():
    janela = paginacao.calcular(57, 3)
    barra = web._barra_paginas(janela, "ficha", "", "")
    assert '<span class="atual">3</span>' in barra
    assert 'href="/?q=ficha&amp;pg=2"' in barra
    assert "anterior" in barra and "seguinte" in barra
    assert "página 3 de 6" in barra


def test_sem_barra_quando_tudo_cabe_numa_pagina():
    assert web._barra_paginas(paginacao.calcular(6, 1), "q", "", "") == ""


def test_barra_da_ultima_pagina_nao_oferece_seguinte():
    barra = web._barra_paginas(paginacao.calcular(57, 6), "q", "", "")
    assert "anterior" in barra
    assert "seguinte" not in barra


def test_abas_so_aparecem_com_mais_de_um_grupo():
    from app.search import seccoes

    documentos = _docs(4)
    grupos = seccoes.agrupar(documentos)
    assert web._abas(documentos, grupos, "q", "", "") == ""


def test_aba_ativa_e_a_da_seccao_aberta():
    from app.search import seccoes

    documentos = _docs(3) + _docs(2, disciplina="Horarios")
    grupos = seccoes.agrupar(documentos)
    if len(grupos) <= 1:
        return
    abas = web._abas(documentos, grupos, "q", "", grupos[0][0].chave)
    assert 'class="aba ativa"' in abas
    assert "Todos" in abas


def test_tempo_usa_virgula_decimal():
    assert web._tempo(0.3141) == " (0,31 segundos)"
    assert web._tempo(0) == ""


def test_fonte_legivel_nao_revela_caminhos_do_disco():
    assert web._fonte_legivel("https://www.sefo.pt/a/b") == "sefo.pt"
    assert web._fonte_legivel("https://moodle.sefo.pt/x") == "moodle.sefo.pt"
    assert web._fonte_legivel(r"C:\Users\ahega\data\raw\psi9\TIC\x.pdf") == "ficheiro"
