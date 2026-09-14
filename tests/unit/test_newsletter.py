"""Os posts: criar, editar, publicar, apagar - e os ids que nao se reciclam."""

from app.models import newsletter


def _ficheiro(tmp_path):
    return tmp_path / "newsletter.json"


def test_base_vazia(tmp_path):
    assert newsletter.listar(caminho=_ficheiro(tmp_path)) == []
    assert newsletter.obter(1, caminho=_ficheiro(tmp_path)) is None
    assert newsletter.contar(caminho=_ficheiro(tmp_path)) == (0, 0)


def test_criar_e_ler(tmp_path):
    caminho = _ficheiro(tmp_path)
    post = newsletter.guardar("Título", "Corpo", "admin-01", caminho=caminho)
    assert post.id == 1
    assert post.titulo == "Título"
    assert post.autor == "admin-01"
    assert post.publicado is False, "um post nasce rascunho"
    assert newsletter.obter(1, caminho=caminho).corpo == "Corpo"


def test_um_post_nasce_rascunho_e_nao_se_ve_de_fora(tmp_path):
    """Da para escrever a meio de uma aula sem ninguem ler por cima do ombro."""
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("Rascunho", "x", "admin-01", caminho=caminho)
    assert newsletter.listar(so_publicados=True, caminho=caminho) == []
    assert len(newsletter.listar(caminho=caminho)) == 1


def test_publicar_e_despublicar(tmp_path):
    caminho = _ficheiro(tmp_path)
    post = newsletter.guardar("T", "C", "admin-01", caminho=caminho)
    newsletter.marcar_publicado(post.id, True, caminho=caminho)
    assert len(newsletter.listar(so_publicados=True, caminho=caminho)) == 1
    newsletter.marcar_publicado(post.id, False, caminho=caminho)
    assert newsletter.listar(so_publicados=True, caminho=caminho) == []


def test_editar_mantem_o_id_o_autor_e_a_data_de_criacao(tmp_path):
    caminho = _ficheiro(tmp_path)
    antes = newsletter.guardar("T", "C", "admin-01", caminho=caminho, agora="2026-09-01T10:00:00")
    depois = newsletter.guardar(
        "Outro", "Outro corpo", "admin-09", identificador=antes.id,
        caminho=caminho, agora="2026-09-05T11:00:00",
    )
    assert depois.id == antes.id
    assert depois.titulo == "Outro"
    assert depois.autor == "admin-01", "o autor e quem escreveu, nao quem editou"
    assert depois.criado == antes.criado
    assert depois.atualizado == "2026-09-05T11:00:00"


def test_editar_nao_mexe_no_estado_de_publicacao_sem_pedir(tmp_path):
    caminho = _ficheiro(tmp_path)
    post = newsletter.guardar("T", "C", "admin-01", publicado=True, caminho=caminho)
    editado = newsletter.guardar(
        "T2", "C2", "admin-01", identificador=post.id, caminho=caminho
    )
    assert editado.publicado is True


def test_ids_nao_se_reciclam(tmp_path):
    """Um id reutilizado fazia uma ligacao antiga apontar para outro texto."""
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("A", "", "admin-01", caminho=caminho)
    segundo = newsletter.guardar("B", "", "admin-01", caminho=caminho)
    newsletter.apagar(segundo.id, caminho=caminho)
    terceiro = newsletter.guardar("C", "", "admin-01", caminho=caminho)
    assert terceiro.id == 3


def test_apagar(tmp_path):
    caminho = _ficheiro(tmp_path)
    post = newsletter.guardar("T", "C", "admin-01", caminho=caminho)
    assert newsletter.apagar(post.id, caminho=caminho) is True
    assert newsletter.apagar(post.id, caminho=caminho) is False
    assert newsletter.listar(caminho=caminho) == []


def test_ordem_do_mais_recente_para_o_mais_antigo(tmp_path):
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("velho", "", "a", caminho=caminho, agora="2026-09-01T08:00:00")
    newsletter.guardar("novo", "", "a", caminho=caminho, agora="2026-09-09T08:00:00")
    assert [p.titulo for p in newsletter.listar(caminho=caminho)] == ["novo", "velho"]


def test_limites_de_tamanho(tmp_path):
    caminho = _ficheiro(tmp_path)
    post = newsletter.guardar(
        "t" * 500, "c" * (newsletter.LIMITE_CORPO + 500), "a", caminho=caminho
    )
    assert len(post.titulo) == newsletter.LIMITE_TITULO
    assert len(post.corpo) == newsletter.LIMITE_CORPO


def test_ficheiro_estragado_nao_rebenta(tmp_path):
    caminho = _ficheiro(tmp_path)
    caminho.write_text("isto nao e JSON", encoding="utf-8")
    assert newsletter.listar(caminho=caminho) == []
    # E continua a dar para escrever por cima.
    assert newsletter.guardar("T", "C", "a", caminho=caminho).id == 1


def test_entrada_sem_campos_e_ignorada(tmp_path):
    import json

    caminho = _ficheiro(tmp_path)
    caminho.write_text(
        json.dumps([{"sem": "id"}, {"id": 4, "titulo": "bom"}]), encoding="utf-8"
    )
    posts = newsletter.listar(caminho=caminho)
    assert [p.titulo for p in posts] == ["bom"]


def test_escrita_e_atomica(tmp_path):
    """Grava ao lado e troca: uma falha a meio nao deixa o ficheiro partido."""
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("T", "C", "a", caminho=caminho)
    assert caminho.exists()
    assert not caminho.with_name(caminho.name + ".novo").exists()


def test_mais_recente_publicado(tmp_path):
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("rascunho", "", "a", caminho=caminho, agora="2026-09-09T08:00:00")
    velho = newsletter.guardar(
        "publicado", "", "a", publicado=True, caminho=caminho, agora="2026-09-01T08:00:00"
    )
    assert newsletter.mais_recente_publicado(caminho=caminho).id == velho.id


def test_contar(tmp_path):
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("a", "", "x", publicado=True, caminho=caminho)
    newsletter.guardar("b", "", "x", caminho=caminho)
    newsletter.guardar("c", "", "x", caminho=caminho)
    assert newsletter.contar(caminho=caminho) == (1, 2)


def test_apagar_o_mais_recente_tambem_nao_recicla(tmp_path):
    """O caso que o contador deduzido do maior id nao cobria."""
    caminho = _ficheiro(tmp_path)
    newsletter.guardar("A", "", "x", caminho=caminho)
    ultimo = newsletter.guardar("B", "", "x", caminho=caminho)
    newsletter.apagar(ultimo.id, caminho=caminho)
    assert newsletter.guardar("C", "", "x", caminho=caminho).id == 3


def test_le_a_forma_antiga_do_ficheiro(tmp_path):
    """Uma lista solta, como o ficheiro nasceu. Nao se parte o que ja esta escrito."""
    import json

    caminho = _ficheiro(tmp_path)
    caminho.write_text(
        json.dumps([
            {"id": 1, "titulo": "velho", "corpo": "c", "autor": "a",
             "criado": "2026-09-01T08:00:00", "atualizado": "2026-09-01T08:00:00",
             "publicado": True}
        ]),
        encoding="utf-8",
    )
    assert [p.titulo for p in newsletter.listar(caminho=caminho)] == ["velho"]
    assert newsletter.guardar("novo", "", "a", caminho=caminho).id == 2
    # E a partir daqui ja esta na forma nova, com contador.
    assert json.loads(caminho.read_text(encoding="utf-8"))["proximo"] == 3
