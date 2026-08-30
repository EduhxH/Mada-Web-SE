"""Testes da parte da busca semantica que nao precisa do modelo.

Fragmentar e preparar sao onde estao as decisoes que se mediram, e sao
deterministas: da para as testar sem carregar 220 MB de pesos.
"""

import numpy as np

from app.search import semantica


def test_texto_curto_fica_num_fragmento():
    texto = "quinze de setembro, inicio das aulas para todos os alunos"
    assert semantica.fragmentar(texto) == [texto]


def test_texto_minusculo_demais_e_descartado():
    assert semantica.fragmentar("ola") == []
    assert semantica.fragmentar("") == []
    assert semantica.fragmentar("   ") == []


def test_texto_longo_e_partido():
    texto = " ".join(["palavra"] * 300)
    fragmentos = semantica.fragmentar(texto)
    assert len(fragmentos) > 1
    for fragmento in fragmentos:
        assert len(fragmento) <= semantica.TAMANHO_FRAGMENTO


def test_fragmentos_nao_comecam_a_meio_de_palavra():
    """O bug que partia "INICIO DAS AULAS" em "...DAS AUL" + "AS PARA...".

    O corte do fim ja caia num espaco, mas o recuo da sobreposicao nao, e era
    o recuo que definia o inicio do fragmento seguinte.
    """
    texto = " ".join(f"palavra{n:03d}" for n in range(200))
    for fragmento in semantica.fragmentar(texto):
        assert fragmento.startswith("palavra"), fragmento[:30]
        assert not fragmento.endswith("palavr")


def test_sobreposicao_preserva_frase_na_fronteira():
    enchimento = "x" * (semantica.TAMANHO_FRAGMENTO - 30)
    texto = f"{enchimento} inicio das aulas para todos os alunos e mais texto aqui"
    fragmentos = semantica.fragmentar(texto)
    assert any("inicio das aulas" in f for f in fragmentos)


def test_texto_sem_espacos_nao_entra_em_ciclo():
    fragmentos = semantica.fragmentar("a" * 2000)
    assert 1 < len(fragmentos) < 50


def test_preparar_baixa_a_caixa():
    """Medido: "INICIO DAS AULAS" da 0.37 contra a pergunta, "inicio" da 0.93."""
    assert semantica.preparar("INICIO DAS AULAS") == "inicio das aulas"


def test_preparar_junta_o_titulo():
    pronto = semantica.preparar("15 de setembro", titulo="Calendario Escolar")
    assert pronto.startswith("calendario escolar.")
    assert "15 de setembro" in pronto


def test_procurar_sem_indice_devolve_vazio():
    assert semantica.procurar(None, "qualquer coisa") == {}


def test_documento_vale_o_seu_melhor_fragmento():
    """Uma pagina com quarenta datas responde pela data certa, nao pela media."""
    vetores = np.array(
        [[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32
    )
    matriz = semantica.Matriz(vetores, np.array([7, 7, 9], dtype=np.int64))

    class ModeloFalso:
        def embed(self, textos):
            return iter([np.array([1.0, 0.0], dtype=np.float32)])

    semantica._modelo = ModeloFalso()
    try:
        pontuacoes = semantica.procurar(matriz, "seja o que for")
    finally:
        semantica._modelo = None

    assert pontuacoes[7] == 1.0  # o melhor fragmento, nao a media com 0.0
    assert round(pontuacoes[9], 3) == 0.6


def test_esquema_e_idempotente(tmp_path):
    import sqlite3

    conexao = sqlite3.connect(tmp_path / "t.sqlite3")
    conexao.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY)")
    semantica.criar_esquema(conexao)
    semantica.criar_esquema(conexao)
    nomes = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "fragmentos" in nomes
