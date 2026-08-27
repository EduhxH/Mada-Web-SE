from app.analytics import uso
from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.interface import disciplina
from app.models.document import Documento


def _indice(tmp_path, documentos):
    disciplina.limpar_cache()
    conexao = storage.abrir(tmp_path / "i.sqlite3")
    indice, tamanhos = construir_indice(documentos)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    return conexao


def _colecao():
    docs = []
    # 9 documentos de Fisica (3 por tema), todos com o mesmo rodape
    temas_fisica = ["radiacao", "temperatura", "termodinamica"]
    for n in range(9):
        docs.append(
            Documento(
                len(docs) + 1,
                f"Fisica {n}",
                f"rodape do professor exemplo {temas_fisica[n % 3]} conteudo",
                "f",
                "Fisica",
            )
        )
    # 6 de Portugues, sem sobreposicao
    for n in range(6):
        docs.append(
            Documento(
                len(docs) + 1, f"Portugues {n}", "gramatica sintaxe texto", "f", "Portugues"
            )
        )
    return docs


def test_boilerplate_nao_entra_nos_temas(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    # "rodape" e "professor" estao em 100% dos docs de Fisica
    assert "rodape" not in disciplina.temas(conexao, "Fisica")
    assert "professor" not in disciplina.temas(conexao, "Fisica")


def test_temas_reais_aparecem(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    encontrados = disciplina.temas(conexao, "Fisica")
    assert "radiacao" in encontrados or "temperatura" in encontrados


def test_nome_da_disciplina_nao_e_tema(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert "fisica" not in disciplina.temas(conexao, "Fisica")


def test_termos_curtos_e_numeros_fora(tmp_path):
    docs = [
        Documento(1, "A", "p2 mod 2025 algoritmo estruturas", "f", "X"),
        Documento(2, "B", "p2 mod 2025 algoritmo listas", "f", "X"),
        Documento(3, "C", "p2 mod 2025 grafos arvores", "f", "X"),
        Documento(4, "D", "outra coisa completamente diferente", "f", "Y"),
    ]
    conexao = _indice(tmp_path, docs)
    encontrados = disciplina.temas(conexao, "X")
    assert "p2" not in encontrados
    assert "mod" not in encontrados
    assert "2025" not in encontrados


def test_disciplina_sem_documentos(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert disciplina.temas(conexao, "Inexistente") == []


def test_cache_devolve_o_mesmo(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert disciplina.temas(conexao, "Fisica") == disciplina.temas(conexao, "Fisica")


def test_pagina_tem_contagem_e_temas(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    registo = uso.abrir(tmp_path / "u.sqlite3")
    html = disciplina.pagina(conexao, registo, "Fisica")
    assert "9 documento(s)" in html
    assert 'class="tema"' in html
    assert "Temas frequentes" in html


def test_pagina_de_disciplina_vazia(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    registo = uso.abrir(tmp_path / "u.sqlite3")
    assert "Nada indexado" in disciplina.pagina(conexao, registo, "Inexistente")


def test_pagina_mostra_consultas_da_turma(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    registo = uso.abrir(tmp_path / "u.sqlite3")
    for aluno in ("aluno-01", "aluno-02"):
        uso.registar(
            registo, aluno, uso.EVENTO_BUSCA,
            consulta="ficha de radiacao", disciplina="Fisica", resultados=3,
        )
    html = disciplina.pagina(conexao, registo, "Fisica")
    assert "ficha de radiacao" in html
    assert "A turma procurou por" in html


def test_consulta_de_um_so_participante_nao_aparece(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    registo = uso.abrir(tmp_path / "u.sqlite3")
    uso.registar(
        registo, "aluno-01", uso.EVENTO_BUSCA,
        consulta="segredo pessoal", disciplina="Fisica", resultados=3,
    )
    assert "segredo pessoal" not in disciplina.pagina(conexao, registo, "Fisica")


def test_pagina_escapa_html(tmp_path):
    docs = [
        Documento(n, f"<script>x{n}</script>", f"conteudo alfa beta gama tema{n % 2}", "f", "X")
        for n in range(1, 8)
    ]
    conexao = _indice(tmp_path, docs)
    registo = uso.abrir(tmp_path / "u.sqlite3")
    html = disciplina.pagina(conexao, registo, "X")
    assert "<script>" not in html
