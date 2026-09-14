"""A varredura de frescura, e sobretudo a identidade de um ficheiro.

O bug que isto guarda: as origens usam **duas** convencoes de ancora, e partir
no primeiro `#` juntava todos os PDF de uma pasta do Moodle num so "ficheiro".
Uma pasta aparecia com 140 paginas e nenhuma copia local lhe correspondia.
"""

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_especificacao = importlib.util.spec_from_file_location(
    "varrer_frescura", RAIZ / "scripts" / "varrer_frescura.py"
)
varredura = importlib.util.module_from_spec(_especificacao)
_especificacao.loader.exec_module(varredura)


@pytest.mark.parametrize(
    "origem,ficheiro,pedivel",
    [
        # Pagina dentro de um PDF servido directamente.
        (
            "https://moodle.sefo.pt/file.php/1/Documentos/horarios.pdf#pagina=27",
            "https://moodle.sefo.pt/file.php/1/Documentos/horarios.pdf",
            "https://moodle.sefo.pt/file.php/1/Documentos/horarios.pdf",
        ),
        # Ficheiro dentro de uma pasta do Moodle, e depois a pagina. Duas ancoras.
        (
            "https://moodle.sefo.pt/mod/folder/view.php?id=82783#Manual.pdf#pagina=8",
            "https://moodle.sefo.pt/mod/folder/view.php?id=82783#Manual.pdf",
            "https://moodle.sefo.pt/mod/folder/view.php?id=82783",
        ),
        # Sem ancora nenhuma: uma pagina do site.
        (
            "https://www.sefo.pt/alumni-em-destaque/",
            "https://www.sefo.pt/alumni-em-destaque/",
            "https://www.sefo.pt/alumni-em-destaque/",
        ),
        # Um `#pagina=` no meio nao e a ancora final; so o do fim conta.
        (
            "https://moodle.sefo.pt/x.php?a=1#pagina=2.pdf#pagina=9",
            "https://moodle.sefo.pt/x.php?a=1#pagina=2.pdf",
            "https://moodle.sefo.pt/x.php?a=1",
        ),
    ],
)
def test_identidade_do_ficheiro(origem, ficheiro, pedivel):
    assert varredura._ficheiro_de(origem) == ficheiro
    assert varredura._pedivel(origem) == pedivel


def test_dois_ficheiros_da_mesma_pasta_sao_ficheiros_diferentes():
    """Era isto que estava errado: a pasta engolia os ficheiros todos."""
    um = "https://moodle.sefo.pt/mod/folder/view.php?id=82160#A.pdf#pagina=1"
    dois = "https://moodle.sefo.pt/mod/folder/view.php?id=82160#B.pdf#pagina=1"
    assert varredura._ficheiro_de(um) != varredura._ficheiro_de(dois)
    # Mas pedem-se ao servidor no mesmo endereco - uma pergunta, nao duas.
    assert varredura._pedivel(um) == varredura._pedivel(dois)


class _Resposta:
    def __init__(self, estado=200, cabecalhos=None):
        self.status_code = estado
        self.headers = cabecalhos or {}


class _Sessao:
    def __init__(self, resposta):
        self._resposta = resposta

    def head(self, *a, **k):
        return self._resposta

    def get(self, *a, **k):
        return self._resposta


def _copia(tmp_path, bytes_=b"x" * 100, quando=None):
    alvo = tmp_path / "copia.pdf"
    alvo.write_bytes(bytes_)
    if quando is not None:
        import os

        os.utime(alvo, (quando, quando))
    return alvo


def test_ficheiro_que_sumiu(tmp_path):
    sessao = _Sessao(_Resposta(404))
    veredicto, porque = varredura.examinar(sessao, "http://x/y.pdf", _copia(tmp_path))
    assert veredicto == varredura.SUMIU
    assert "404" in porque


def test_publicado_depois_da_nossa_copia(tmp_path):
    """O caso do horario: o mesmo endereco, ficheiro novo."""
    import datetime

    nossa = datetime.datetime(2026, 7, 10, tzinfo=datetime.timezone.utc).timestamp()
    sessao = _Sessao(
        _Resposta(200, {"Last-Modified": "Mon, 14 Sep 2026 08:00:00 GMT"})
    )
    veredicto, porque = varredura.examinar(
        sessao, "http://x/horarios.pdf", _copia(tmp_path, quando=nossa)
    )
    assert veredicto == varredura.MUDOU
    assert "depois da nossa copia" in porque


def test_tamanho_diferente_denuncia_a_troca(tmp_path):
    import datetime

    nossa = datetime.datetime(2026, 9, 14, tzinfo=datetime.timezone.utc).timestamp()
    sessao = _Sessao(
        _Resposta(200, {"Last-Modified": "Mon, 01 Sep 2026 08:00:00 GMT",
                        "Content-Length": "999"})
    )
    veredicto, porque = varredura.examinar(
        sessao, "http://x/y.pdf", _copia(tmp_path, quando=nossa)
    )
    assert veredicto == varredura.MUDOU
    assert "999" in porque


def test_igual_e_fresco(tmp_path):
    import datetime

    nossa = datetime.datetime(2026, 9, 14, tzinfo=datetime.timezone.utc).timestamp()
    sessao = _Sessao(
        _Resposta(200, {"Last-Modified": "Mon, 01 Sep 2026 08:00:00 GMT",
                        "Content-Length": "100"})
    )
    veredicto, _ = varredura.examinar(
        sessao, "http://x/y.pdf", _copia(tmp_path, quando=nossa)
    )
    assert veredicto == varredura.FRESCO


def test_pagina_gerada_na_hora_nao_e_defeito(tmp_path):
    """Sem data nem tamanho nao ha comparacao possivel - e um limite, nao um bug."""
    sessao = _Sessao(_Resposta(200, {"Content-Type": "text/html"}))
    veredicto, _ = varredura.examinar(sessao, "http://x/", _copia(tmp_path))
    assert veredicto == varredura.NAO_VERIFICAVEL


def test_sem_copia_local_nao_da_veredicto(tmp_path):
    sessao = _Sessao(_Resposta(200, {"Content-Length": "10"}))
    veredicto, porque = varredura.examinar(sessao, "http://x/y.pdf", None)
    assert veredicto == varredura.SEM_RESPOSTA
    assert "copia local" in porque
