"""Quem esta online, de que aparelho, e ha quanto tempo."""

from datetime import datetime, timedelta, timezone

import pytest

from app.analytics import uso
from app.interface import presenca

AGORA = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)


def _ha(segundos: int) -> str:
    return (AGORA - timedelta(seconds=segundos)).isoformat(timespec="seconds")


# ------------------------------------------------------------ aparelhos


@pytest.mark.parametrize(
    "agente,esperado",
    [
        # Telemoveis
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15",
         presenca.TELEMOVEL),
        ("Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile Safari/537",
         presenca.TELEMOVEL),
        ("Mozilla/5.0 (Windows Phone 10.0) Edge/15", presenca.TELEMOVEL),
        # Tablets: o iPad diz "Mobile" na mesma cadeia em que diz "iPad", e um
        # tablet Android diz "Android" SEM dizer "Mobi". E por isso que o tablet
        # e testado primeiro e o Android por ultimo.
        ("Mozilla/5.0 (iPad; CPU OS 17_0) AppleWebKit/605.1.15 Mobile/15E148",
         presenca.TABLET),
        ("Mozilla/5.0 (Linux; Android 13; SM-X200) Chrome/120 Safari/537",
         presenca.TABLET),
        # Computadores
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537",
         presenca.COMPUTADOR),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Safari/605", presenca.COMPUTADOR),
        ("Mozilla/5.0 (X11; Linux x86_64) Firefox/120", presenca.COMPUTADOR),
        # Sem cadeia nenhuma
        ("", presenca.DESCONHECIDO),
        (None, presenca.DESCONHECIDO),
    ],
)
def test_aparelho_pelo_agente(agente, esperado):
    assert presenca.dispositivo_de(agente) == esperado


# -------------------------------------------------------------- caminhos


@pytest.mark.parametrize(
    "caminho,esperado",
    [
        ("/", "busca"),
        ("", "busca"),
        ("/?q=horario+psi9", "busca"),
        ("/novidades", "novidades"),
        ("/documento?id=412&q=criterios", "documento"),
        ("/painel/utilizadores", "painel"),
    ],
)
def test_caminho_reduzido_a_uma_palavra(caminho, esperado):
    """Guardar a consulta aqui era guardar duas vezes a mesma coisa sobre alguem."""
    assert presenca.pagina_de(caminho) == esperado


def test_o_caminho_nunca_leva_a_consulta():
    assert "criterios" not in presenca.pagina_de("/documento?id=1&q=criterios")


# ---------------------------------------------------------------- online


def test_esta_online_dentro_da_janela():
    assert presenca.esta_online(_ha(10), AGORA) is True
    assert presenca.esta_online(_ha(uso.SEGUNDOS_ONLINE - 1), AGORA) is True


def test_deixa_de_estar_online_depois_da_janela():
    assert presenca.esta_online(_ha(uso.SEGUNDOS_ONLINE + 1), AGORA) is False


def test_quem_nunca_apareceu():
    assert presenca.esta_online(None, AGORA) is False
    assert presenca.segundos_desde(None) is None
    assert presenca.segundos_desde("nao e uma data") is None


def test_marca_sem_fuso_horario_conta_como_utc():
    """O SQLite devolve o que la foi posto; sem fuso, assume-se UTC."""
    sem_fuso = AGORA.replace(tzinfo=None).isoformat(timespec="seconds")
    assert presenca.segundos_desde(sem_fuso, AGORA) == 0


@pytest.mark.parametrize(
    "segundos,esperado",
    [
        (None, "nunca entrou"),
        (0, "agora mesmo"),
        (59, "agora mesmo"),
        (60, "há 1 min"),
        (3599, "há 59 min"),
        (3600, "há 1 h"),
        (7200, "há 2 h"),
        (86400, "ontem"),
        (172800, "há 2 dias"),
    ],
)
def test_ha_quanto_tempo(segundos, esperado):
    assert presenca.ha_quanto_tempo(segundos) == esperado


# ------------------------------------------------------------- escritas


def test_a_escrita_e_estrangulada(tmp_path, monkeypatch):
    """Escrever a cada pedido era escrever cem vezes mais do que a informacao muda."""
    caminho = tmp_path / "uso.sqlite3"
    monkeypatch.setattr(uso, "CAMINHO_USO", caminho)
    uso.fechar_partilhada()
    presenca.esquecer_cache()

    escritas = []
    original = uso.marcar_presenca
    monkeypatch.setattr(
        uso, "marcar_presenca",
        lambda *a, **k: (escritas.append(a), original(*a, **k))[1],
    )

    for _ in range(20):
        presenca.marcar("aluno-01", "Mozilla/5.0 (iPhone)", "/")
    assert len(escritas) == 1, "vinte pedidos seguidos, uma escrita"

    conexao = uso.partilhada()
    guardado = uso.presencas(conexao)["aluno-01"]
    assert guardado["dispositivo"] == presenca.TELEMOVEL
    assert guardado["pagina"] == "busca"
    uso.fechar_partilhada()
    presenca.esquecer_cache()


def test_marcar_nunca_levanta(monkeypatch):
    """Isto corre no caminho de cada pedido: nao pode derrubar uma busca."""
    presenca.esquecer_cache()

    def rebenta(*a, **k):
        raise RuntimeError("a base de dados esta trancada")

    monkeypatch.setattr(uso, "partilhada", rebenta)
    presenca.marcar("aluno-01", "Mozilla/5.0", "/")
    presenca.esquecer_cache()


def test_pedido_sem_agente_nao_apaga_o_aparelho_conhecido(tmp_path, monkeypatch):
    """Uma sonda sem User-Agent nao pode fazer esquecer o telemovel de alguem."""
    caminho = tmp_path / "uso.sqlite3"
    conexao = uso.abrir(caminho)
    uso.marcar_presenca(conexao, "aluno-01", presenca.TELEMOVEL, "busca")
    uso.marcar_presenca(conexao, "aluno-01", None, "novidades")
    guardado = uso.presencas(conexao)["aluno-01"]
    assert guardado["dispositivo"] == presenca.TELEMOVEL
    assert guardado["pagina"] == "novidades"
