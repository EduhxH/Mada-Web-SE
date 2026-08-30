from app.models.document import Documento
from app.search import agrupamento


def _doc(doc_id, origem, titulo="t"):
    return Documento(doc_id, titulo, "texto", origem, "d")


def _par(doc_id, origem, pontuacao=1.0):
    return (_doc(doc_id, origem), pontuacao)


def test_ficheiro_ignora_o_numero_de_pagina():
    assert agrupamento.ficheiro_de("https://x/a.pdf#pagina=3") == "https://x/a.pdf"
    assert agrupamento.ficheiro_de("https://x/b.pptx#slide=12") == "https://x/b.pptx"


def test_ficheiro_sem_marcador_fica_igual():
    assert agrupamento.ficheiro_de("https://x/cursos") == "https://x/cursos"


def test_so_o_marcador_final_e_removido():
    """A origem do Moodle traz o nome do ficheiro tambem depois de um #."""
    origem = "https://m/view.php?id=82783#Planificacao.pdf#pagina=8"
    assert agrupamento.ficheiro_de(origem) == (
        "https://m/view.php?id=82783#Planificacao.pdf"
    )


def test_paginas_do_mesmo_ficheiro_dao_um_grupo():
    grupos = agrupamento.agrupar_por_ficheiro([
        _par(1, "https://x/a.pdf#pagina=1", 0.9),
        _par(2, "https://x/a.pdf#pagina=7", 0.8),
        _par(3, "https://x/a.pdf#pagina=3", 0.7),
    ])
    assert len(grupos) == 1
    assert grupos[0].paginas == 3
    assert grupos[0].documento.id == 1  # a melhor pagina lidera


def test_ordem_de_relevancia_e_mantida():
    grupos = agrupamento.agrupar_por_ficheiro([
        _par(1, "https://x/a.pdf#pagina=1", 0.9),
        _par(2, "https://x/b.pdf#pagina=1", 0.8),
        _par(3, "https://x/a.pdf#pagina=2", 0.7),
    ])
    assert [g.documento.id for g in grupos] == [1, 2]
    assert grupos[0].paginas == 2
    assert not grupos[1].tem_mais


def test_ficheiros_diferentes_nao_se_juntam():
    grupos = agrupamento.agrupar_por_ficheiro([
        _par(1, "https://x/a.pdf#pagina=1"),
        _par(2, "https://x/b.pdf#pagina=1"),
    ])
    assert len(grupos) == 2


def test_lista_vazia():
    assert agrupamento.agrupar_por_ficheiro([]) == []


def test_achatar_devolve_uma_por_ficheiro():
    grupos = agrupamento.agrupar_por_ficheiro([
        _par(1, "https://x/a.pdf#pagina=1"),
        _par(2, "https://x/a.pdf#pagina=9"),
        _par(3, "https://x/b.pdf"),
    ])
    assert [d.id for d, _ in agrupamento.achatar(grupos)] == [1, 3]


def _doc_texto(doc_id, origem, texto):
    return (Documento(doc_id, "t", texto, origem, "d"), 1.0)


def test_mesmo_conteudo_em_pastas_diferentes_junta_se():
    """A mesma ficha em quatro pastas do Moodle ocupava quatro lugares."""
    texto = "conteudo identico " * 20
    grupos = agrupamento.agrupar_por_ficheiro([
        _doc_texto(1, "https://m/view.php?id=82281#Ficha.pdf#pagina=1", texto),
        _doc_texto(2, "https://m/view.php?id=82267#Ficha.pdf#pagina=1", texto),
        _doc_texto(3, "https://m/view.php?id=82260#Ficha.pdf#pagina=1", texto),
    ])
    assert len(grupos) == 1
    assert grupos[0].copias == 2


def test_conteudos_diferentes_nao_se_juntam():
    grupos = agrupamento.agrupar_por_ficheiro([
        _doc_texto(1, "https://m/a.pdf", "primeiro texto bem comprido " * 10),
        _doc_texto(2, "https://m/b.pdf", "segundo texto bem comprido " * 10),
    ])
    assert len(grupos) == 2


def test_texto_curto_nao_junta_nada():
    """Duas paginas quase vazias nao sao o mesmo documento."""
    grupos = agrupamento.agrupar_por_ficheiro([
        _doc_texto(1, "https://m/a.pdf", "ola"),
        _doc_texto(2, "https://m/b.pdf", "ola"),
    ])
    assert len(grupos) == 2


def test_juntar_copias_pode_ser_desligado():
    texto = "conteudo identico " * 20
    grupos = agrupamento.agrupar_por_ficheiro([
        _doc_texto(1, "https://m/a.pdf", texto),
        _doc_texto(2, "https://m/b.pdf", texto),
    ], juntar_copias=False)
    assert len(grupos) == 2


def test_data_legivel():
    from app.interface import web

    assert web._data_legivel("2026-07-24") == "jul 2026"
    assert web._data_legivel("2026-05-13") == "mai 2026"


def test_data_invalida_nao_aparece():
    from app.interface import web

    for bruta in ("", "ontem", "2026", "2026-13-01", "2026-00-01"):
        assert web._data_legivel(bruta) == ""
