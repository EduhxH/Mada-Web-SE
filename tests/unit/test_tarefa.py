"""A decisao que isto guarda: reindexar custa dois minutos, e nao se paga por nada.

Tres corridas por dia durante setembro sao noventa. Se cada uma reindexasse o
corpus inteiro so porque correu, eram tres horas de CPU gastas a confirmar que
ninguem publicou nada. O teste que importa aqui e o negativo: `atualizar` NAO e
chamado quando nao houve novidade.
"""

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_especificacao = importlib.util.spec_from_file_location(
    "tarefa", RAIZ / "scripts" / "tarefa.py"
)
tarefa = importlib.util.module_from_spec(_especificacao)
_especificacao.loader.exec_module(tarefa)


class ProgramaFalso:
    """Faz de `main` sem tocar na rede nem no indice."""

    SAIDA_FALHA = 1
    SAIDA_NOVIDADE = 10

    def __init__(self, verificar=0, horario=0, texto_horario="") -> None:
        self._verificar = verificar
        self._horario = horario
        self._texto_horario = texto_horario
        self.reindexou = 0
        self.verificou = 0

    def comando_verificar_moodle(self, disciplinas, intervalo):
        self.verificou += 1
        return self._verificar

    def comando_horario(self, forcar=False):
        if self._texto_horario:
            print(self._texto_horario)
        return self._horario

    def comando_atualizar(self, url, paginas, intervalo, sem_rastreio=False):
        assert sem_rastreio, "a tarefa diaria nao pode rastrear o site inteiro"
        self.reindexou += 1


def _nada():
    pass


def test_conteudos_sem_novidade_nao_reindexa():
    programa = ProgramaFalso(verificar=0)
    assert tarefa.passo_conteudos(programa, _nada) == 0
    assert programa.reindexou == 0


def test_conteudos_com_novidade_reindexa():
    programa = ProgramaFalso(verificar=ProgramaFalso.SAIDA_NOVIDADE)
    assert tarefa.passo_conteudos(programa, _nada) == 0
    assert programa.reindexou == 1


def test_conteudos_que_falha_nao_reindexa_e_sai_a_um():
    """Sem rede, o corpus e o de ontem: reindexa-lo nao acrescenta nada."""
    programa = ProgramaFalso(verificar=ProgramaFalso.SAIDA_FALHA)
    assert tarefa.passo_conteudos(programa, _nada) == 1
    assert programa.reindexou == 0


def test_horario_fora_da_janela_nao_escreve_no_registo():
    """De hora a hora, quase sempre nao ha nada: vinte e quatro linhas por dia
    a dizer 'nada a fazer' enterravam as vezes em que houve."""
    programa = ProgramaFalso(horario=0, texto_horario="Nada a fazer: hoje nao sai.")
    marcas = []
    assert tarefa.passo_horario(programa, lambda: marcas.append(1)) == 0
    assert marcas == []
    assert programa.reindexou == 0


def test_horario_sem_mudanca_escreve_porque_houve_rede():
    programa = ProgramaFalso(horario=0, texto_horario="O horario publicado ainda e o mesmo.")
    marcas = []
    assert tarefa.passo_horario(programa, lambda: marcas.append(1)) == 0
    assert marcas == [1]
    assert programa.reindexou == 0


def test_horario_novo_reindexa():
    programa = ProgramaFalso(
        horario=ProgramaFalso.SAIDA_NOVIDADE, texto_horario="Horario novo."
    )
    assert tarefa.passo_horario(programa, _nada) == 0
    assert programa.reindexou == 1


def test_horario_que_falha_sai_a_um_e_fica_registado():
    programa = ProgramaFalso(horario=ProgramaFalso.SAIDA_FALHA, texto_horario="erro")
    marcas = []
    assert tarefa.passo_horario(programa, lambda: marcas.append(1)) == 1
    assert marcas == [1]
    assert programa.reindexou == 0


def test_registo_aceita_tudo_e_nao_rebenta_sem_consola(tmp_path):
    registo = tarefa.Registo(tmp_path / "a" / "b.log", None)
    registo.write("linha\n")
    registo.flush()
    assert not registo.isatty()
    registo.fechar()
    assert (tmp_path / "a" / "b.log").read_text(encoding="utf-8") == "linha\n"


def test_registo_nao_deixa_o_ecra_quebrado_matar_a_tarefa(tmp_path):
    class EcraQuebrado:
        def write(self, texto):
            raise OSError("a consola desapareceu")

        def flush(self):
            raise OSError("idem")

    registo = tarefa.Registo(tmp_path / "b.log", EcraQuebrado())
    registo.write("continua a escrever no ficheiro\n")
    registo.fechar()
    assert "continua" in (tmp_path / "b.log").read_text(encoding="utf-8")


def test_registo_roda_quando_cresce(tmp_path, monkeypatch):
    monkeypatch.setattr(tarefa, "BYTES_MAXIMOS", 10)
    caminho = tmp_path / "c.log"
    caminho.write_text("x" * 50, encoding="utf-8")
    tarefa.Registo(caminho, None).fechar()
    assert (tmp_path / "c.log.1").read_text(encoding="utf-8") == "x" * 50
    assert caminho.read_text(encoding="utf-8") == ""


def test_passo_desconhecido_e_recusado_pelo_argparse(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tarefa.py", "inventado"])
    with pytest.raises(SystemExit):
        tarefa.main()


def test_correr_escreve_o_rebentamento_no_registo(tmp_path, monkeypatch):
    """Uma tarefa agendada nao tem ecra: se morre em silencio, ninguem soube."""
    import sys

    def explodir(programa, encabecar):
        raise RuntimeError("o disco encheu")

    monkeypatch.setitem(tarefa.PASSOS, "conteudos", explodir)
    antes = sys.stdout
    assert tarefa.correr("conteudos", "manha", raiz=tmp_path) == 1
    assert sys.stdout is antes, "o stdout tem de voltar ao que era"
    texto = (tmp_path / "data" / "verificacao.log").read_text(encoding="utf-8")
    assert "[manha]" in texto
    assert "REBENTOU" in texto and "o disco encheu" in texto
