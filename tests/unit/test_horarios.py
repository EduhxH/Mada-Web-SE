"""A regra de quando verificar e o coracao disto, e e testavel sem rede."""

from datetime import datetime

from app.crawler import horarios


def quinta(hora):
    return datetime(2026, 9, 17, hora)      # quinta-feira


def sexta(hora):
    return datetime(2026, 9, 18, hora)      # sexta-feira


def sabado(hora):
    return datetime(2026, 9, 19, hora)      # sabado


def domingo(hora):
    return datetime(2026, 9, 20, hora)      # domingo


def segunda(hora):
    return datetime(2026, 9, 21, hora)      # segunda-feira


def test_quinta_de_manha_ainda_nao():
    verificar, motivo = horarios.deve_verificar(quinta(9), {})
    assert not verificar
    assert "cedo" in motivo


def test_quinta_a_tarde_sim():
    assert horarios.deve_verificar(quinta(12), {})[0]
    assert horarios.deve_verificar(quinta(17), {})[0]


def test_sexta_a_tarde_sim():
    assert not horarios.deve_verificar(sexta(11), {})[0]
    assert horarios.deve_verificar(sexta(13), {})[0]


def test_fim_de_semana_a_qualquer_hora():
    """Se nao saiu na quinta nem na sexta, ainda pode sair no fim de semana."""
    assert horarios.deve_verificar(sabado(3), {})[0]
    assert horarios.deve_verificar(domingo(23), {})[0]


def test_dias_de_semana_nao_se_verifica():
    for dia in (datetime(2026, 9, 14, 15), datetime(2026, 9, 15, 15),
                datetime(2026, 9, 16, 15)):
        verificar, motivo = horarios.deve_verificar(dia, {})
        assert not verificar
        assert "nao sai" in motivo


def test_semana_ja_resolvida_nao_volta_a_incomodar():
    """Apanhado na quinta, nao se verifica mais ate a quinta seguinte."""
    estado = {"semana_resolvida": horarios.semana_de(quinta(13))}
    for momento in (quinta(18), sexta(13), sabado(10), domingo(20)):
        verificar, motivo = horarios.deve_verificar(momento, estado)
        assert not verificar
        assert "ja foi apanhado" in motivo


def test_semana_nova_recomeca_a_vigia():
    estado = {"semana_resolvida": horarios.semana_de(quinta(13))}
    quinta_seguinte = datetime(2026, 9, 24, 13)
    assert horarios.deve_verificar(quinta_seguinte, estado)[0]


def test_quinta_sexta_sabado_e_domingo_sao_a_mesma_semana():
    """A semana ISO comeca a segunda: os quatro dias de vigia caem na mesma,
    e por isso "ja saiu esta semana" e uma pergunta so."""
    semanas = {horarios.semana_de(m) for m in (quinta(13), sexta(13), sabado(1), domingo(23))}
    assert len(semanas) == 1
    assert horarios.semana_de(segunda(9)) != horarios.semana_de(quinta(13))


def test_estado_corrompido_nao_derruba(tmp_path):
    caminho = tmp_path / "estado.json"
    caminho.write_text("{isto nao e json", encoding="utf-8")
    assert horarios.ler_estado(caminho) == {}


def test_estado_ida_e_volta(tmp_path):
    caminho = tmp_path / "estado.json"
    horarios.guardar_estado({"marca": "abc", "semana_resolvida": "2026-S38"}, caminho)
    assert horarios.ler_estado(caminho)["marca"] == "abc"
