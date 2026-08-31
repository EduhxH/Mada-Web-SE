"""Detalhes de apresentacao que so se veem abrindo a pagina."""

from app.interface import web
from app.models.document import Documento


def _doc(doc_id, disciplina="Escola", titulo="Titulo"):
    return (Documento(doc_id, titulo, "texto com palavras suficientes", "o", disciplina), 1.0)


def test_contagem_concorda_em_numero():
    assert web._contagem(1) == "1 resultado"
    assert web._contagem(32) == "32 resultados"
    assert web._contagem(0) == "0 resultados"


def test_etiqueta_de_disciplina_so_quando_distingue():
    """Cinco resultados todos de "Escola": cinco etiquetas que nada separam."""
    assert not web._distingue_disciplina([_doc(1), _doc(2), _doc(3)])
    assert web._distingue_disciplina([_doc(1, "Escola"), _doc(2, "TIC")])


def test_lista_vazia_nao_distingue():
    assert not web._distingue_disciplina([])


def test_pontuacao_escondida_por_omissao():
    """E um numero de depuracao: nenhum aluno sabe o que e."""
    doc, pontos = _doc(1)
    assert 'class="pontuacao"' not in web._um_resultado(doc, pontos, "q", 1, {"texto"})


def test_pontuacao_visivel_para_administrador():
    doc, pontos = _doc(1)
    html = web._um_resultado(doc, pontos, "q", 1, {"texto"}, mostrar_pontuacao=True)
    assert 'class="pontuacao"' in html


def test_etiqueta_pode_ser_desligada():
    doc, pontos = _doc(1, "TIC")
    com = web._um_resultado(doc, pontos, "q", 1, {"texto"}, mostrar_disciplina=True)
    sem = web._um_resultado(doc, pontos, "q", 1, {"texto"}, mostrar_disciplina=False)
    assert "TIC" in com
    assert 'class="disciplina"' not in sem
