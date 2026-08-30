from app.models.document import Documento
from app.search import hibrida, intencao


def test_deteta_disciplina_escrita_na_pergunta():
    assert intencao.detetar_disciplina("sebenta de fisica")[0] == "Física-Química"
    assert intencao.detetar_disciplina("trabalho de portugues")[0] == "Português"
    assert intencao.detetar_disciplina("manual de tic")[0] == "TIC"


def test_alcunha_mais_longa_ganha():
    """"educacao fisica" nao pode ser lida como "fisica"."""
    assert intencao.detetar_disciplina(
        "exercicios de educacao fisica"
    )[0] == "Educação Física"


def test_sem_disciplina_nao_inventa():
    assert intencao.detetar_disciplina("regulamento interno")[0] is None
    assert intencao.detetar_disciplina("")[0] is None


def test_nome_da_disciplina_sai_da_consulta():
    _, resto = intencao.detetar_disciplina("sebenta de fisica")
    assert resto == "sebenta"


def test_disciplina_sozinha_mantem_a_consulta():
    """Se so escreveu a disciplina, nao ha termos para procurar."""
    disciplina, resto = intencao.detetar_disciplina("portugues")
    assert disciplina == "Português"
    assert resto.strip()


def test_so_conta_disciplina_que_existe_no_indice():
    assert intencao.detetar_disciplina("sebenta de fisica", ["TIC"])[0] is None


def test_deteta_pedido_de_recencia():
    assert intencao.pede_recente("ultima ficha de portugues")
    assert intencao.pede_recente("trabalho mais recente")
    assert not intencao.pede_recente("regulamento interno")


def test_marcas_de_recencia_saem_da_consulta():
    assert intencao.limpar_recencia("ultima ficha de portugues") == (
        "ficha de portugues"
    )


def _doc(doc_id, data):
    return (Documento(doc_id, "t", "x", "o", "d", data), 1.0)


def test_ordenar_por_data_poe_recentes_primeiro():
    ordenados = hibrida.ordenar_por_data(
        [_doc(1, "2025-01-01"), _doc(2, "2026-06-01"), _doc(3, "2025-09-01")]
    )
    assert [d.id for d, _ in ordenados] == [2, 3, 1]


def test_sem_data_vai_para_o_fim():
    """Sem data nao ha como afirmar que e recente: nao se inventa."""
    ordenados = hibrida.ordenar_por_data(
        [_doc(1, ""), _doc(2, "2026-06-01"), _doc(3, "")]
    )
    assert [d.id for d, _ in ordenados][0] == 2
    assert {d.id for d, _ in ordenados[1:]} == {1, 3}


def _doc_disc(doc_id, disciplina, pontuacao=1.0):
    return (Documento(doc_id, "t", "x", "o", disciplina), pontuacao)


def test_disciplina_nomeada_vem_antes_da_escola():
    """"trabalho de ingles" devolvia "Higiene e Seguranca no Trabalho":
    "Escola" sao 57% da colecao e ganhava por peso bruto."""
    ordenados = hibrida.realcar_disciplina(
        [_doc_disc(1, "Escola", 0.9), _doc_disc(2, "Inglês", 0.2)], "Inglês"
    )
    assert [d.id for d, _ in ordenados] == [2, 1]


def test_documentos_da_escola_nao_desaparecem():
    """Os criterios de avaliacao de TIC vivem no site, nao no Moodle."""
    ordenados = hibrida.realcar_disciplina(
        [_doc_disc(1, "Escola", 0.9), _doc_disc(2, "TIC", 0.2)], "TIC"
    )
    assert len(ordenados) == 2
    assert 1 in [d.id for d, _ in ordenados]


def test_ordem_dentro_de_cada_metade_e_mantida():
    ordenados = hibrida.realcar_disciplina(
        [
            _doc_disc(1, "Escola", 0.9), _doc_disc(2, "TIC", 0.8),
            _doc_disc(3, "Escola", 0.7), _doc_disc(4, "TIC", 0.6),
        ],
        "TIC",
    )
    assert [d.id for d, _ in ordenados] == [2, 4, 1, 3]


def test_sem_disciplina_nada_muda():
    entrada = [_doc_disc(1, "Escola"), _doc_disc(2, "TIC")]
    assert hibrida.realcar_disciplina(entrada, "") == entrada
