from app.models.document import Documento
from app.search import seccoes


def _doc(titulo, origem="data/raw/psi9/M/f.pdf", disciplina="Matematica", doc_id=1):
    return Documento(doc_id, titulo, "texto", origem, disciplina)


def test_horarios_pela_disciplina():
    assert seccoes.classificar(_doc("horarios - pagina 3", disciplina="Horários")) == (
        seccoes.HORARIOS
    )


def test_regulamento_pelo_titulo():
    assert seccoes.classificar(_doc("REGULAMENTO INTERNO APROVADO")) == (
        seccoes.REGULAMENTOS
    )
    assert seccoes.classificar(_doc("Criterios de Avaliacao TIC")) == (
        seccoes.REGULAMENTOS
    )
    assert seccoes.classificar(_doc("Planificacao Modular M4")) == seccoes.REGULAMENTOS


def test_regulamento_vence_pagina_do_site():
    doc = _doc("Regulamento Interno", origem="https://www.sefo.pt/reg.pdf")
    assert seccoes.classificar(doc) == seccoes.REGULAMENTOS


def test_pagina_do_site():
    doc = _doc("Cursos Profissionais", origem="https://www.sefo.pt/cursos")
    assert seccoes.classificar(doc) == seccoes.SITE


def test_material_por_omissao():
    assert seccoes.classificar(_doc("FichaDiagnostico - pagina 1")) == seccoes.MATERIAL


def test_ata_nao_apanha_data():
    # "ata" dentro de "data" nao pode disparar a regra
    assert seccoes.classificar(_doc("Tratamento de Dados")) == seccoes.MATERIAL
    assert seccoes.classificar(_doc("Ata da reuniao")) == seccoes.REGULAMENTOS


def test_agrupar_ordena_pela_melhor_pontuacao():
    resultados = [
        (_doc("Cursos", origem="https://x/a", doc_id=1), 0.9),
        (_doc("Ficha 1", doc_id=2), 0.5),
        (_doc("Regulamento", doc_id=3), 0.8),
    ]
    grupos = seccoes.agrupar(resultados)
    assert [g.chave for g, _ in grupos] == [
        seccoes.SITE,
        seccoes.REGULAMENTOS,
        seccoes.MATERIAL,
    ]


def test_agrupar_mantem_a_ordem_dentro_da_seccao():
    resultados = [
        (_doc("Ficha A", doc_id=1), 0.9),
        (_doc("Ficha B", doc_id=2), 0.7),
        (_doc("Ficha C", doc_id=3), 0.3),
    ]
    (_, itens), = seccoes.agrupar(resultados)
    assert [doc.id for doc, _ in itens] == [1, 2, 3]


def test_filtrar_devolve_so_a_seccao():
    resultados = [
        (_doc("Ficha", doc_id=1), 0.9),
        (_doc("Regulamento", doc_id=2), 0.8),
    ]
    assert [d.id for d, _ in seccoes.filtrar(resultados, seccoes.MATERIAL)] == [1]


def test_agrupar_lista_vazia():
    assert seccoes.agrupar([]) == []


def test_titulo_de_chave_desconhecida():
    assert seccoes.titulo_da("inexistente") == ""
