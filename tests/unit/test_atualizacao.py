from app.indexing import atualizacao


def _escrever(pasta, nome, texto):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(texto, encoding="utf-8")


def _correr(tmp_path):
    return atualizacao.reindexar(
        raiz=tmp_path / "raw", banco=tmp_path / "indice.sqlite3"
    )


def test_primeira_indexacao_e_tudo_novo(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar e calor")
    _escrever(tmp_path / "raw" / "Fisica", "b.txt", "ondas e frequencia")
    alteracoes, _, termos = _correr(tmp_path)
    assert len(alteracoes.novos) == 2
    assert alteracoes.mantidos == 0
    assert termos > 0


def test_sem_alteracoes(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar e calor")
    _correr(tmp_path)
    alteracoes, _, _ = _correr(tmp_path)
    assert not alteracoes.houve_mudanca
    assert alteracoes.mantidos == 1


def test_ficheiro_novo_e_detetado(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar")
    _correr(tmp_path)
    _escrever(tmp_path / "raw" / "Fisica", "b.txt", "ondas sonoras")
    alteracoes, _, _ = _correr(tmp_path)
    assert len(alteracoes.novos) == 1
    assert alteracoes.mantidos == 1
    assert alteracoes.novos[0][1] == "b"


def test_ficheiro_alterado_e_detetado(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar")
    _correr(tmp_path)
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar e tambem calor")
    alteracoes, _, _ = _correr(tmp_path)
    assert len(alteracoes.alterados) == 1
    assert not alteracoes.novos


def test_ficheiro_removido_e_detetado(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar")
    _escrever(tmp_path / "raw" / "Fisica", "b.txt", "ondas sonoras")
    _correr(tmp_path)
    (tmp_path / "raw" / "Fisica" / "b.txt").unlink()
    alteracoes, _, _ = _correr(tmp_path)
    assert len(alteracoes.removidos) == 1
    assert alteracoes.removidos[0][1] == "b"
    assert alteracoes.mantidos == 1


def test_mover_ficheiro_conta_como_novo_e_removido(tmp_path):
    """A origem faz parte do id: mudar de disciplina e outro documento."""
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar")
    _correr(tmp_path)
    (tmp_path / "raw" / "Fisica" / "a.txt").unlink()
    _escrever(tmp_path / "raw" / "Quimica", "a.txt", "radiacao solar")
    alteracoes, _, _ = _correr(tmp_path)
    assert len(alteracoes.novos) == 1
    assert len(alteracoes.removidos) == 1


def test_corpus_vazio_nao_rebenta(tmp_path):
    (tmp_path / "raw").mkdir()
    alteracoes, _, termos = _correr(tmp_path)
    assert not alteracoes.houve_mudanca
    assert termos == 0


def test_resumo_legivel(tmp_path):
    _escrever(tmp_path / "raw" / "Fisica", "a.txt", "radiacao solar")
    alteracoes, _, _ = _correr(tmp_path)
    assert "1 novos" in alteracoes.resumo()
