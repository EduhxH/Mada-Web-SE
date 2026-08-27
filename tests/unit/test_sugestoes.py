from app.analytics import uso
from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.models.document import Documento
from app.search import sugestoes


def _uso(tmp_path):
    return uso.abrir(tmp_path / "uso.sqlite3")


def _indice(tmp_path):
    conexao = storage.abrir(tmp_path / "indice.sqlite3")
    documentos = [
        Documento(1, "A", "matematica derivadas integrais", "f", "Matematica"),
        Documento(2, "B", "matematica funcoes", "f", "Matematica"),
        Documento(3, "C", "matriz identidade", "f", "Matematica"),
        Documento(4, "D", "portugues gramatica", "f", "Portugues"),
    ]
    indice, tamanhos = construir_indice(documentos)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    return conexao


def _busca(conexao, participante, consulta, resultados=3):
    uso.registar(
        conexao, participante, uso.EVENTO_BUSCA, consulta=consulta, resultados=resultados
    )


def test_prefixo_curto_nao_sugere(tmp_path):
    r = sugestoes.sugerir(_uso(tmp_path), _indice(tmp_path), "aluno-01", "m")
    assert r == []


def test_historico_proprio_vem_primeiro(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-01", "matematica ficha 3")
    _busca(u, "aluno-02", "matematica teste")
    _busca(u, "aluno-03", "matematica teste")
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "mat")
    assert r[0].texto == "matematica ficha 3"
    assert r[0].origem == sugestoes.ORIGEM_HISTORICO


def test_popular_exige_dois_participantes(tmp_path):
    u = _uso(tmp_path)
    # so um participante: nao deve aparecer como popular
    _busca(u, "aluno-02", "matematica segredo pessoal")
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "mat")
    textos = [s.texto for s in r]
    assert "matematica segredo pessoal" not in textos


def test_popular_aparece_com_dois_participantes(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-02", "matematica derivadas")
    _busca(u, "aluno-03", "matematica derivadas")
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "mat")
    assert any(
        s.texto == "matematica derivadas" and s.origem == sugestoes.ORIGEM_POPULAR
        for s in r
    )


def test_consultas_sem_resultado_nao_sao_sugeridas(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-01", "matematica inexistente", resultados=0)
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "mat")
    assert "matematica inexistente" not in [s.texto for s in r]


def test_vocabulario_completa_quando_nao_ha_historico(tmp_path):
    r = sugestoes.sugerir(_uso(tmp_path), _indice(tmp_path), "aluno-01", "mat")
    textos = [s.texto for s in r]
    assert "matematica" in textos
    assert "matriz" in textos
    assert all(s.origem == sugestoes.ORIGEM_VOCABULARIO for s in r)


def test_vocabulario_completa_so_a_ultima_palavra(tmp_path):
    r = sugestoes.sugerir(_uso(tmp_path), _indice(tmp_path), "aluno-01", "ficha mat")
    assert "ficha matematica" in [s.texto for s in r]


def test_nao_sugere_o_que_ja_esta_escrito(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-01", "matematica")
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "matematica")
    assert "matematica" not in [s.texto for s in r]


def test_sem_duplicados_entre_fontes(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-01", "matematica")
    _busca(u, "aluno-02", "matematica")
    _busca(u, "aluno-03", "matematica")
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "mate")
    textos = [s.texto for s in r]
    assert len(textos) == len(set(textos))


def test_caracteres_de_like_sao_escapados(tmp_path):
    u = _uso(tmp_path)
    _busca(u, "aluno-01", "matematica")
    # "%" faria o LIKE casar com tudo se nao fosse escapado
    r = sugestoes.sugerir(u, _indice(tmp_path), "aluno-01", "%%")
    assert r == []


def test_respeita_o_limite(tmp_path):
    r = sugestoes.sugerir(_uso(tmp_path), _indice(tmp_path), "aluno-01", "ma", limite=1)
    assert len(r) <= 1
