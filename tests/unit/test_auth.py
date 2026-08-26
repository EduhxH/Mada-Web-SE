import time

from app.interface import auth


def _isolar(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CAMINHO_PARTICIPANTES", tmp_path / "p.json")
    monkeypatch.setattr(auth, "CAMINHO_SEGREDO", tmp_path / "s.txt")
    monkeypatch.setattr(auth, "CAMINHO_ENV", tmp_path / "nao-existe.env")
    monkeypatch.setattr(auth, "_env_carregado", True)
    monkeypatch.delenv(auth.VAR_SEGREDO, raising=False)


def test_codigo_tem_formato_legivel():
    codigo = auth.gerar_codigo()
    assert len(codigo) == 9
    assert codigo[4] == "-"
    assert not set(codigo.replace("-", "")) & set("O0I1")


def test_codigos_sao_distintos():
    assert len({auth.gerar_codigo() for _ in range(200)}) == 200


def test_sessao_valida_devolve_o_participante():
    chave = b"segredo-de-teste"
    sessao = auth.criar_sessao("aluno-03", chave)
    assert auth.validar_sessao(sessao, chave) == "aluno-03"


def test_sessao_com_chave_errada_e_recusada():
    sessao = auth.criar_sessao("aluno-03", b"chave-certa")
    assert auth.validar_sessao(sessao, b"chave-errada") is None


def test_sessao_adulterada_e_recusada():
    chave = b"segredo-de-teste"
    sessao = auth.criar_sessao("aluno-03", chave)
    _, emitido, assinatura = sessao.split("|")
    assert auth.validar_sessao(f"aluno-99|{emitido}|{assinatura}", chave) is None


def test_sessao_expirada_e_recusada():
    chave = b"segredo-de-teste"
    antigo = int(time.time()) - (auth.VALIDADE_DIAS + 1) * 86400
    corpo = f"aluno-01|{antigo}"
    assinatura = auth._assinar(corpo, chave)
    assert auth.validar_sessao(f"{corpo}|{assinatura}", chave) is None


def test_sessao_malformada_nao_rebenta():
    assert auth.validar_sessao("lixo", b"k") is None
    assert auth.validar_sessao("a|b|c|d", b"k") is None
    assert auth.validar_sessao("aluno|nao-e-numero|abc", b"k") is None


def test_codigo_valido_e_reconhecido(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    novos = auth.criar_participantes(1)
    codigo = next(iter(novos))
    assert auth.participante_do_codigo(codigo) == "aluno-01"
    assert auth.participante_do_codigo(codigo.lower()) == "aluno-01"
    assert auth.participante_do_codigo("ZZZZ-ZZZZ") is None
    assert auth.participante_do_codigo("") is None


def test_ficheiro_nao_guarda_codigos_em_claro(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    novos = auth.criar_participantes(2)
    guardado = (tmp_path / "p.json").read_text(encoding="utf-8")
    for codigo in novos:
        assert codigo not in guardado
    for chave in auth.carregar_participantes():
        assert len(chave) == 64


def test_codigos_antigos_em_claro_sao_migrados(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.guardar_participantes({"AAAA-BBBB": "aluno-01"})
    assert auth.participante_do_codigo("AAAA-BBBB") == "aluno-01"
    assert "AAAA-BBBB" not in (tmp_path / "p.json").read_text(encoding="utf-8")


def test_revogar_remove_so_um(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    novos = auth.criar_participantes(3)
    codigos = {rotulo: codigo for codigo, rotulo in novos.items()}
    assert auth.revogar("aluno-02") is True
    assert auth.revogar("aluno-99") is False
    assert auth.participante_do_codigo(codigos["aluno-02"]) is None
    assert auth.participante_do_codigo(codigos["aluno-01"]) == "aluno-01"


def test_segredo_vem_da_variavel_de_ambiente(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    monkeypatch.setenv(auth.VAR_SEGREDO, "segredo-de-ambiente")
    assert auth.segredo() == b"segredo-de-ambiente"
    assert not (tmp_path / "s.txt").exists()


def test_env_e_lido_quando_existe(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    env = tmp_path / "teste.env"
    linhas = ["# comentario", 'MADALENA_SEGREDO="do-ficheiro"', ""]
    env.write_text("\n".join(linhas), encoding="utf-8")
    monkeypatch.setattr(auth, "CAMINHO_ENV", env)
    monkeypatch.setattr(auth, "_env_carregado", False)
    assert auth.segredo() == b"do-ficheiro"


def test_criar_participantes_nao_apaga_os_antigos(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(3)
    auth.criar_participantes(2)
    participantes = auth.carregar_participantes()
    assert len(participantes) == 5
    assert set(participantes.values()) == {f"aluno-{n:02d}" for n in range(1, 6)}
