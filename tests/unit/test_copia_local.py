"""Encontrar em disco a copia que o indice descreve, e decidir se se serve.

O que isto guarda: o Moodle serve o material das pastas com
`Content-Disposition: attachment` e exige sessao iniciada, e para os ficheiros
dentro de pastas o endereco guardado e o da **pasta** - quem clicava aterrava
numa listagem, a descarregar, sem a pagina certa. Servir a nossa copia resolve
as tres coisas; este ficheiro guarda as regras de quando o fazemos.
"""

import json

import pytest

from app.interface import copia_local

PNG = b"nao importa o conteudo"


@pytest.fixture(autouse=True)
def _isolar(tmp_path, monkeypatch):
    raiz = (tmp_path / "raw").resolve()
    raiz.mkdir()
    monkeypatch.setattr(copia_local, "RAIZ_DADOS", raiz)
    copia_local.esquecer_cache()
    yield raiz
    copia_local.esquecer_cache()


def _manifesto(raiz, pasta, entradas, ficheiros=None):
    destino = raiz / pasta
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "_origens.json").write_text(
        json.dumps(entradas, ensure_ascii=False), encoding="utf-8"
    )
    for nome, dados in (ficheiros or {}).items():
        (destino / nome).write_bytes(dados)
    return destino


# ------------------------------------------------------- tirar a pagina


@pytest.mark.parametrize(
    "origem,esperado",
    [
        ("https://x/a.pdf#pagina=27", "https://x/a.pdf"),
        ("https://x/a.pdf#slide=3", "https://x/a.pdf"),
        ("https://x/a.pdf", "https://x/a.pdf"),
        # Duas ancoras: um ficheiro dentro de uma pasta do Moodle. So a ultima
        # e que se tira - partir no primeiro `#` juntava a pasta inteira num so
        # documento.
        (
            "https://x/view.php?id=8#Manual.pdf#pagina=8",
            "https://x/view.php?id=8#Manual.pdf",
        ),
        # Um `#pagina=` que nao e o numero final fica onde esta.
        ("https://x/a.pdf#pagina=abc", "https://x/a.pdf#pagina=abc"),
    ],
)
def test_sem_pagina(origem, esperado):
    assert copia_local._sem_pagina(origem) == esperado


@pytest.mark.parametrize(
    "origem,pagina",
    [
        ("https://x/a.pdf#pagina=27", 27),
        ("https://x/view.php?id=8#Manual.pdf#pagina=8", 8),
        ("https://x/a.pptx#slide=3", 3),
        ("https://x/a.pdf", None),
        ("https://x/a.pdf#pagina=nao", None),
    ],
)
def test_pagina_de(origem, pagina):
    assert copia_local.pagina_de(origem) == pagina


# --------------------------------------------------------- encontrar


def test_encontra_pela_origem_sem_a_pagina(_isolar):
    _manifesto(
        _isolar, "psi9",
        {"folder-1-manual-abc.pdf": {"url": "https://m/view.php?id=8#Manual.pdf"}},
        {"folder-1-manual-abc.pdf": PNG},
    )
    alvo = copia_local.caminho_de("https://m/view.php?id=8#Manual.pdf#pagina=8")
    assert alvo is not None
    assert alvo.name == "folder-1-manual-abc.pdf"


def test_manifesto_com_url_em_texto_simples(_isolar):
    """O rastreio do site guarda so a cadeia; o do Moodle guarda um objeto."""
    _manifesto(
        _isolar, "Escola",
        {"uploads-Regulamento-abc.pdf": "https://www.sefo.pt/uploads/Regulamento.pdf"},
        {"uploads-Regulamento-abc.pdf": PNG},
    )
    alvo = copia_local.caminho_de(
        "https://www.sefo.pt/uploads/Regulamento.pdf#pagina=5"
    )
    assert alvo is not None


def test_dois_ficheiros_da_mesma_pasta_nao_se_confundem(_isolar):
    _manifesto(
        _isolar, "psi9",
        {
            "folder-1-a.pdf": {"url": "https://m/view.php?id=8#A.pdf"},
            "folder-1-b.pdf": {"url": "https://m/view.php?id=8#B.pdf"},
        },
        {"folder-1-a.pdf": b"aaa", "folder-1-b.pdf": b"bbb"},
    )
    a = copia_local.caminho_de("https://m/view.php?id=8#A.pdf#pagina=1")
    b = copia_local.caminho_de("https://m/view.php?id=8#B.pdf#pagina=1")
    assert a.read_bytes() == b"aaa"
    assert b.read_bytes() == b"bbb"


def test_origem_desconhecida(_isolar):
    _manifesto(_isolar, "psi9", {}, {})
    assert copia_local.caminho_de("https://m/nunca-visto.pdf") is None
    assert copia_local.caminho_de("") is None
    assert copia_local.ha_copia("https://m/nunca-visto.pdf") is False


def test_manifesto_que_aponta_para_ficheiro_que_nao_existe(_isolar):
    _manifesto(_isolar, "psi9", {"sumiu.pdf": {"url": "https://m/x.pdf"}})
    assert copia_local.caminho_de("https://m/x.pdf") is None


# ----------------------------------------------------- o que NAO se serve


def test_pagina_html_do_site_nao_se_serve(_isolar):
    """Servida daqui perdia estilo, menus e imagens - e abre bem la fora."""
    _manifesto(
        _isolar, "Escola",
        {"alumni-abc.html": "https://www.sefo.pt/alumni/"},
        {"alumni-abc.html": b"<html></html>"},
    )
    assert copia_local.caminho_de("https://www.sefo.pt/alumni/") is None


def test_zip_nao_se_serve(_isolar):
    _manifesto(
        _isolar, "psi9", {"pacote.zip": {"url": "https://m/p.zip"}},
        {"pacote.zip": b"PK"},
    )
    assert copia_local.caminho_de("https://m/p.zip") is None


def test_ficheiro_grande_demais_manda_para_a_origem(_isolar, monkeypatch):
    """Ha um PDF de 117 MB: por aqui passava pelo tunel e pela ligacao de casa."""
    monkeypatch.setattr(copia_local, "LIMITE_SERVIR", 100)
    _manifesto(
        _isolar, "psi9", {"gordo.pdf": {"url": "https://m/g.pdf"}},
        {"gordo.pdf": b"x" * 500},
    )
    assert copia_local.caminho_de("https://m/g.pdf") is None
    _manifesto(
        _isolar, "psi9b", {"magro.pdf": {"url": "https://m/m.pdf"}},
        {"magro.pdf": b"x" * 50},
    )
    copia_local.esquecer_cache()
    assert copia_local.caminho_de("https://m/m.pdf") is not None


def test_manifesto_nao_deixa_sair_da_raiz(_isolar):
    """O manifesto e um ficheiro em disco: nao se confia nele para apontar fora."""
    fora = _isolar.parent / "segredo.pdf"
    fora.write_bytes(b"nao devia sair")
    _manifesto(
        _isolar, "psi9",
        {"../segredo.pdf": {"url": "https://m/x.pdf"}},
    )
    assert copia_local.caminho_de("https://m/x.pdf") is None


@pytest.mark.parametrize(
    "conteudo", ["nao e json", "[]", '"uma cadeia"', "null", "123"]
)
def test_manifesto_estragado_nao_rebenta(_isolar, conteudo):
    destino = _isolar / "psi9"
    destino.mkdir(parents=True)
    (destino / "_origens.json").write_text(conteudo, encoding="utf-8")
    assert copia_local.caminho_de("https://m/x.pdf") is None


# ------------------------------------------------------------- a cache


def test_a_cache_nota_material_novo(_isolar, monkeypatch):
    """As tarefas agendadas trazem material tres vezes por dia, noutro processo."""
    monkeypatch.setattr(copia_local, "SEGUNDOS_ENTRE_VERIFICACOES", 0)
    _manifesto(
        _isolar, "psi9", {"um.pdf": {"url": "https://m/1.pdf"}}, {"um.pdf": PNG}
    )
    assert copia_local.ha_copia("https://m/1.pdf")
    assert not copia_local.ha_copia("https://m/2.pdf")

    _manifesto(
        _isolar, "psi9",
        {"um.pdf": {"url": "https://m/1.pdf"}, "dois.pdf": {"url": "https://m/2.pdf"}},
        {"dois.pdf": PNG},
    )
    assert copia_local.ha_copia("https://m/2.pdf"), "nao viu o que entrou depois"


def test_a_cache_nao_vai_ao_disco_a_cada_chamada(_isolar, monkeypatch):
    """Perguntar sempre custava 5,5 ms, e isto e chamado por cada resultado."""
    _manifesto(
        _isolar, "psi9", {"um.pdf": {"url": "https://m/1.pdf"}}, {"um.pdf": PNG}
    )
    copia_local.ha_copia("https://m/1.pdf")

    vezes = []
    original = copia_local._marca_dos_manifestos
    monkeypatch.setattr(
        copia_local, "_marca_dos_manifestos",
        lambda: (vezes.append(1), original())[1],
    )
    for _ in range(50):
        copia_local.ha_copia("https://m/1.pdf")
    assert vezes == [], "foi ao disco dentro da janela de estrangulamento"
