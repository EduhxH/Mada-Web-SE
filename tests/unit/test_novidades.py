from datetime import date

from app.models import novidades


def _caminho(tmp_path):
    return tmp_path / "novidades.json"


def test_registo_vazio_nao_cria_ficheiro(tmp_path):
    caminho = _caminho(tmp_path)
    assert novidades.registar([], caminho) == 0
    assert not caminho.exists()


def test_regista_e_le(tmp_path):
    caminho = _caminho(tmp_path)
    entradas = [("TIC", "Ficha 3", "/mod/resource/view.php?id=1")]
    assert novidades.registar(entradas, caminho, quando=date(2026, 8, 30)) == 1

    lidas = novidades.recentes(7, caminho, hoje=date(2026, 8, 30))
    assert len(lidas) == 1
    assert lidas[0].disciplina == "TIC"
    assert lidas[0].titulo == "Ficha 3"


def test_repetidos_nao_duplicam(tmp_path):
    """A verificacao pode correr duas vezes no mesmo dia."""
    caminho = _caminho(tmp_path)
    entradas = [("TIC", "Ficha 3", "/mod/resource/view.php?id=1")]
    novidades.registar(entradas, caminho, quando=date(2026, 8, 30))
    assert novidades.registar(entradas, caminho, quando=date(2026, 8, 30)) == 0
    assert len(novidades.recentes(7, caminho, hoje=date(2026, 8, 30))) == 1


def test_antigas_saem_da_janela(tmp_path):
    caminho = _caminho(tmp_path)
    novidades.registar(
        [("TIC", "Antiga", "/mod/resource/view.php?id=1")],
        caminho, quando=date(2026, 8, 1),
    )
    novidades.registar(
        [("TIC", "Nova", "/mod/resource/view.php?id=2")],
        caminho, quando=date(2026, 8, 29),
    )
    recentes = novidades.recentes(7, caminho, hoje=date(2026, 8, 30))
    assert [n.titulo for n in recentes] == ["Nova"]
    assert novidades.contar_recentes(7, caminho, hoje=date(2026, 8, 30)) == 1


def test_ordena_da_mais_recente_para_a_mais_antiga(tmp_path):
    caminho = _caminho(tmp_path)
    for dia, titulo in ((26, "A"), (29, "B"), (27, "C")):
        novidades.registar(
            [("TIC", titulo, f"/mod/resource/view.php?id={dia}")],
            caminho, quando=date(2026, 8, dia),
        )
    lidas = novidades.recentes(7, caminho, hoje=date(2026, 8, 30))
    assert [n.titulo for n in lidas] == ["B", "C", "A"]


def test_ficheiro_corrompido_nao_derruba_a_leitura(tmp_path):
    caminho = _caminho(tmp_path)
    caminho.write_text("isto nao e json", encoding="utf-8")
    assert novidades.recentes(7, caminho) == []
    assert novidades.registar(
        [("TIC", "Ficha", "/mod/resource/view.php?id=9")], caminho
    ) == 1


def test_entrada_malformada_e_saltada(tmp_path):
    import json

    caminho = _caminho(tmp_path)
    caminho.write_text(
        json.dumps([
            {"data": "2026-08-29", "disciplina": "TIC", "titulo": "Boa", "url": "/1"},
            {"disciplina": "TIC"},
            {"data": "nao-e-data", "disciplina": "TIC", "titulo": "Ma", "url": "/2"},
        ]),
        encoding="utf-8",
    )
    lidas = novidades.recentes(7, caminho, hoje=date(2026, 8, 30))
    assert [n.titulo for n in lidas] == ["Boa"]


def test_registo_nao_cresce_sem_limite(tmp_path):
    import json

    caminho = _caminho(tmp_path)
    for n in range(novidades.MAXIMO_ENTRADAS + 40):
        novidades.registar(
            [("TIC", f"Ficha {n}", f"/mod/resource/view.php?id={n}")],
            caminho, quando=date(2026, 8, 30),
        )
    guardadas = json.loads(caminho.read_text(encoding="utf-8"))
    assert len(guardadas) == novidades.MAXIMO_ENTRADAS
    # as ultimas sobrevivem, as primeiras e que saem
    assert guardadas[-1]["titulo"] == f"Ficha {novidades.MAXIMO_ENTRADAS + 39}"


def test_pagina_escapa_titulos(tmp_path, monkeypatch):
    """Os titulos vem do Moodle: nunca podem entrar crus no HTML."""
    from app.interface import web

    caminho = _caminho(tmp_path)
    novidades.registar(
        [("TIC", "<script>alerta</script>", "/mod/resource/view.php?id=1")],
        caminho, quando=date.today(),
    )
    monkeypatch.setattr(novidades, "CAMINHO_PADRAO", caminho)

    pagina = web._pagina_novidades()
    assert "<script>alerta</script>" not in pagina
    assert "&lt;script&gt;" in pagina


def test_aviso_some_quando_nao_ha_nada(tmp_path, monkeypatch):
    from app.interface import web

    monkeypatch.setattr(novidades, "CAMINHO_PADRAO", _caminho(tmp_path))
    assert web._aviso_novidades() == ""


def test_aviso_concorda_em_numero(tmp_path, monkeypatch):
    from app.interface import web

    caminho = _caminho(tmp_path)
    monkeypatch.setattr(novidades, "CAMINHO_PADRAO", caminho)

    novidades.registar(
        [("TIC", "Uma", "/mod/resource/view.php?id=1")], caminho, quando=date.today()
    )
    assert "1 documento novo" in web._aviso_novidades()

    novidades.registar(
        [("TIC", "Outra", "/mod/resource/view.php?id=2")], caminho, quando=date.today()
    )
    assert "2 documentos novos" in web._aviso_novidades()
