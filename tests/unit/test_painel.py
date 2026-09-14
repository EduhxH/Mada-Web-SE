"""O painel: avisos, operacoes, e o HTML que sai de cada secao.

O que se guarda aqui e sobretudo a barreira e o escape. O desenho muda; que o
painel nao mostre a um aluno o que e do administrador, e que um rotulo escrito
a mao nao vire HTML, nao muda.
"""

import json

import pytest

from app.analytics import uso
from app.interface import auth, avisos, media, operacoes, painel, presenca
from app.models import newsletter


@pytest.fixture
def registo(tmp_path, monkeypatch):
    """Um mundo isolado: base de dados, participantes, posts e media em tmp."""
    monkeypatch.setattr(auth, "CAMINHO_PARTICIPANTES", tmp_path / "p.json")
    monkeypatch.setattr(auth, "CAMINHO_SEGREDO", tmp_path / "s.txt")
    monkeypatch.setattr(auth, "CAMINHO_CORTES", tmp_path / "cortes.json")
    monkeypatch.setattr(auth, "CAMINHO_ENV", tmp_path / "nao-existe.env")
    monkeypatch.setattr(auth, "_env_carregado", True)
    monkeypatch.setattr(auth, "_cache_rotulos", None)
    monkeypatch.setattr(auth, "_cache_epocas", None)
    monkeypatch.delenv(auth.VAR_SEGREDO, raising=False)
    monkeypatch.setattr(newsletter, "CAMINHO_PADRAO", tmp_path / "newsletter.json")
    monkeypatch.setattr(media, "PASTA", tmp_path / "media")
    monkeypatch.setattr(media, "PASTA_PERFIL", tmp_path / "perfil")
    monkeypatch.setattr(avisos, "CAMINHO", tmp_path / "visto.json")
    monkeypatch.setattr(painel, "CAMINHO_BANCO", tmp_path / "nao-ha-indice.sqlite3")
    operacoes.reiniciar_para_testes()
    painel._recados.clear()
    auth.criar_participantes(1, "admin")
    auth.criar_participantes(3, "aluno")
    return uso.abrir(tmp_path / "uso.sqlite3")


# ------------------------------------------------------------- desenhar


@pytest.mark.parametrize("seccao", painel.CHAVES)
def test_todas_as_secoes_desenham(seccao, registo):
    pagina = painel.pagina(seccao, "admin-01", registo)
    assert pagina.startswith("<!doctype html>")
    assert pagina.rstrip().endswith("</html>")
    assert 'class="pn-grelha"' in pagina


def test_a_secao_aberta_fica_marcada_na_navegacao(registo):
    pagina = painel.pagina(painel.UTILIZADORES, "admin-01", registo)
    assert '<a class="ativa" href="/painel/utilizadores">' in pagina


def test_seccao_desconhecida_cai_na_visao_geral(registo):
    assert "Estatísticas" in painel.pagina("inventada", "admin-01", registo)


def test_a_pagina_desenha_mesmo_sem_indice(registo):
    """As sete da manha do dia da apresentacao, isto tem de abrir na mesma."""
    pagina = painel.pagina(painel.VISAO, "admin-01", registo)
    assert "falta indexar" in pagina


def test_todos_os_participantes_aparecem_na_tabela(registo):
    pagina = painel.pagina(painel.UTILIZADORES, "admin-01", registo)
    for rotulo in ("admin-01", "aluno-01", "aluno-02", "aluno-03"):
        assert f'data-quem="{rotulo}"' in pagina


def test_o_admin_nao_se_pode_revogar_a_si_mesmo(registo):
    """Revogar-se deixava o painel sem ninguem que o abrisse."""
    pagina = painel.pagina(painel.UTILIZADORES, "admin-01", registo)
    corte = pagina[pagina.index('data-quem="admin-01"'):]
    corte = corte[: corte.index("</tr>")]
    assert 'value="revogar"' not in corte
    assert "não te podes revogar a ti mesmo" in corte


def test_o_aluno_pode_ser_revogado(registo):
    pagina = painel.pagina(painel.UTILIZADORES, "admin-01", registo)
    corte = pagina[pagina.index('data-quem="aluno-01"'):]
    corte = corte[: corte.index("</tr>")]
    assert 'value="revogar"' in corte


def test_o_simbolo_de_formulario_esta_em_todos_os_formularios(registo):
    for seccao in (painel.UTILIZADORES, painel.AUTOMATIZACAO, painel.PERFIL):
        pagina = painel.pagina(seccao, "admin-01", registo)
        assert 'name="csrf"' in pagina
        assert auth.simbolo_csrf("admin-01") in pagina


# --------------------------------------------------------------- escape


def test_um_recado_nao_pode_trazer_HTML(registo):
    """O recado leva nomes vindos de um formulario. So o admin os escreve - e
    "so o admin" nao e razao para nao escapar: e o caminho mais curto para um
    XSS em si proprio."""
    painel.deixar_recado("admin-01", "<script>alert(1)</script>", mau=True)
    contexto = painel.tirar_recado("admin-01")
    pagina = painel.pagina(painel.UTILIZADORES, "admin-01", registo, contexto)
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;" in pagina


def test_o_recado_mostra_se_uma_vez(registo):
    painel.deixar_recado("admin-01", "guardado")
    assert painel.tirar_recado("admin-01")["recado"] == "guardado"
    assert painel.tirar_recado("admin-01") == {}


def test_o_recado_e_de_quem_o_pediu(registo):
    painel.deixar_recado("admin-01", "so para mim")
    assert painel.tirar_recado("admin-09") == {}
    assert painel.tirar_recado("admin-01")["recado"] == "so para mim"


def test_o_titulo_de_um_post_e_escapado(registo):
    newsletter.guardar("<img src=x onerror=alert(1)>", "corpo", "admin-01")
    pagina = painel.pagina(painel.NEWSLETTER, "admin-01", registo)
    assert "<img src=x onerror=alert(1)>" not in pagina
    assert "&lt;img" in pagina


def test_a_previa_do_editor_vem_ja_renderizada(registo):
    post = newsletter.guardar("T", "## Título\n\n**forte**", "admin-01")
    pagina = painel.pagina(
        painel.NEWSLETTER, "admin-01", registo, {"post": post}
    )
    assert '<h2 class="nl-titulo">Título</h2>' in pagina
    assert "<strong>forte</strong>" in pagina


def test_o_registo_e_escapado_na_consola(registo):
    from app.interface import registo as registo_servidor

    registo_servidor.anotar(
        registo_servidor.INFO, 'GET /?q=<script>alert(1)</script>', "http"
    )
    pagina = painel.pagina(painel.REGISTO, "admin-01", registo)
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;" in pagina
    registo_servidor.limpar()


# ---------------------------------------------------------------- avisos


def test_sem_marca_o_painel_abre_limpo(registo):
    """A primeira visita nao mostra tudo o que ja aconteceu como se fosse novo."""
    uso.registar(registo, "aluno-01", uso.EVENTO_BUSCA, consulta="x", resultados=1)
    contas = avisos.contar(registo)
    assert contas[avisos.VISAO] == 0


def test_um_evento_no_mesmo_segundo_da_marca_conta(registo):
    """Com carimbos ao segundo, este evento ficava para sempre por contar.

    E o caso que se ve todos os dias: abre-se o painel e alguem pesquisa no
    mesmo instante.
    """
    avisos.marcar_visto(avisos.VISAO, registo)
    uso.registar(registo, "aluno-01", uso.EVENTO_BUSCA, consulta="x", resultados=1)
    assert avisos.contar(registo)[avisos.VISAO] == 1


def test_o_ponto_aparece_com_o_que_veio_depois(registo):
    avisos.marcar_visto(avisos.VISAO, registo)
    uso.registar(registo, "aluno-01", uso.EVENTO_BUSCA, consulta="x", resultados=1)
    uso.registar(registo, "aluno-02", uso.EVENTO_BUSCA, consulta="y", resultados=1)
    assert avisos.contar(registo)[avisos.VISAO] == 2


def test_abrir_a_secao_apaga_o_seu_ponto(registo):
    avisos.marcar_visto(avisos.UTILIZADORES, registo)
    uso.registar(registo, "aluno-01", uso.EVENTO_ENTRADA)
    assert avisos.contar(registo)[avisos.UTILIZADORES] == 1
    painel.pagina(painel.UTILIZADORES, "admin-01", registo)
    assert avisos.contar(registo)[avisos.UTILIZADORES] == 0


def test_uma_operacao_falhada_poe_ponto_na_automatizacao(registo):
    assert avisos.contar(registo)[avisos.AUTOMATIZACAO] == 0
    operacoes._estados[operacoes.CONTEUDOS].bem = False
    assert avisos.contar(registo)[avisos.AUTOMATIZACAO] == 1


def test_etiqueta_do_ponto():
    assert avisos.etiqueta(0) == ""
    assert avisos.etiqueta(-3) == ""
    assert avisos.etiqueta(1) == "1"
    assert avisos.etiqueta(9) == "9"
    assert avisos.etiqueta(400) == "9+"


def test_contar_nunca_levanta(registo):
    """O painel inteiro depende disto para se desenhar."""

    class Partida:
        def execute(self, *a, **k):
            raise RuntimeError("trancada")

    assert avisos.contar(Partida())[avisos.VISAO] == 0


# ------------------------------------------------------------- operacoes


def test_operacao_desconhecida_e_recusada():
    operacoes.reiniciar_para_testes()
    comecou, porque = operacoes.iniciar("formatar-o-disco")
    assert comecou is False
    assert "desconhecida" in porque


def test_so_corre_uma_de_cada_vez(monkeypatch):
    """Duas ao mesmo tempo entravam duas vezes no Moodle e reindexavam em paralelo."""
    import threading

    operacoes.reiniciar_para_testes()
    segura = threading.Event()
    monkeypatch.setattr(
        operacoes, "_passo_conteudos", lambda escrever: (segura.wait(5), (True, "ok"))[1]
    )
    assert operacoes.iniciar(operacoes.CONTEUDOS)[0] is True
    assert operacoes.ocupado() == operacoes.CONTEUDOS
    comecou, porque = operacoes.iniciar(operacoes.HORARIO)
    assert comecou is False
    assert "já está a correr" in porque
    segura.set()


def test_uma_operacao_que_rebenta_fica_registada(monkeypatch):
    import time

    operacoes.reiniciar_para_testes()

    def rebenta(escrever):
        raise RuntimeError("o Moodle nao respondeu")

    monkeypatch.setattr(operacoes, "_passo_horario", rebenta)
    operacoes.iniciar(operacoes.HORARIO)
    for _ in range(60):
        if not operacoes.estado(operacoes.HORARIO).a_correr:
            break
        time.sleep(0.05)
    estado = operacoes.estado(operacoes.HORARIO)
    assert estado.bem is False
    assert "rebentou" in estado.resumo
    assert operacoes.ocupado() is None


def test_json_vivo_traz_so_o_que_foi_pedido(registo):
    dados = json.loads(painel.json_vivo(registo, "registo"))
    assert set(dados) == {"registo"}
    dados = json.loads(painel.json_vivo(registo, "presenca,operacoes"))
    assert set(dados) == {"presenca", "operacoes", "ocupado"}
    assert json.loads(painel.json_vivo(registo, "")) == {}


def test_json_vivo_diz_quem_esta_online(registo):
    uso.marcar_presenca(registo, "aluno-01", presenca.TELEMOVEL, "busca")
    dados = json.loads(painel.json_vivo(registo, "presenca"))
    pessoas = {p["rotulo"]: p for p in dados["presenca"]}
    assert pessoas["aluno-01"]["online"] is True
    assert pessoas["aluno-01"]["aparelho"] == presenca.TELEMOVEL
    assert pessoas["aluno-02"]["online"] is False
    assert pessoas["aluno-02"]["visto"] == "nunca entrou"


def test_json_previa_usa_o_renderizador_do_servidor():
    saida = json.loads(painel.json_previa("<script>x</script> **b**"))["html"]
    assert "<script>" not in saida
    assert "<strong>b</strong>" in saida
