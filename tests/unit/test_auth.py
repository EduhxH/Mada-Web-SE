import time

from app.interface import auth


def _isolar(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CAMINHO_PARTICIPANTES", tmp_path / "p.json")
    monkeypatch.setattr(auth, "CAMINHO_SEGREDO", tmp_path / "s.txt")
    # As epocas de sessao tambem. Sem isto os testes escreviam no ficheiro real,
    # e correr a bateria com o servidor no ar expulsava a turma inteira.
    monkeypatch.setattr(auth, "CAMINHO_CORTES", tmp_path / "cortes.json")
    monkeypatch.setattr(auth, "_cache_epocas", None)
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
    _, epoca, emitido, assinatura = sessao.split("|")
    adulterada = f"aluno-99|{epoca}|{emitido}|{assinatura}"
    assert auth.validar_sessao(adulterada, chave) is None


def test_epoca_adulterada_e_recusada():
    """A epoca vai dentro do que e assinado - subi-la a mao nao serve de nada."""
    chave = b"segredo-de-teste"
    participante, epoca, emitido, assinatura = auth.criar_sessao(
        "aluno-03", chave
    ).split("|")
    subida = f"{participante}|{int(epoca) + 1}|{emitido}|{assinatura}"
    assert auth.validar_sessao(subida, chave) is None


def test_sessao_expirada_e_recusada():
    chave = b"segredo-de-teste"
    antigo = int(time.time()) - (auth.VALIDADE_DIAS + 1) * 86400
    corpo = f"aluno-01|0|{antigo}"
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


def test_numeracao_conta_cada_prefixo_por_si(tmp_path, monkeypatch):
    """O bug que isto fecha: cinco alunos davam `admin-06` ao primeiro admin."""
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(5, "aluno")
    novos = auth.criar_participantes(1, "admin")
    assert set(novos.values()) == {"admin-01"}
    seguintes = auth.criar_participantes(2, "aluno")
    assert set(seguintes.values()) == {"aluno-06", "aluno-07"}


def test_numeracao_retoma_do_maior_e_nao_da_contagem(tmp_path, monkeypatch):
    """Revogar o do meio nao pode reciclar o rotulo: seria outra pessoa."""
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(3)
    auth.revogar("aluno-02")
    novos = auth.criar_participantes(1)
    assert set(novos.values()) == {"aluno-04"}


def test_rotulos_manuais_nao_rebentam_a_numeracao(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.guardar_participantes({"h1": "aluno-professora", "h2": "aluno-02"})
    assert set(auth.criar_participantes(1).values()) == {"aluno-03"}


def test_zerar_revoga_tudo(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    novos = auth.criar_participantes(3)
    codigo = next(iter(novos))
    assert auth.zerar_participantes() == 3
    assert auth.carregar_participantes() == {}
    assert auth.participante_do_codigo(codigo) is None


def test_zerar_base_vazia_nao_rebenta(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert auth.zerar_participantes() == 0


def test_sessao_de_codigo_revogado_deixa_de_valer(tmp_path, monkeypatch):
    """O buraco que isto tapa: `--revogar` nao revogava nada durante 30 dias."""
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(3)
    chave = auth.segredo()
    cookie = auth.criar_sessao("aluno-02", chave)
    assert auth.participante_da_sessao(cookie, chave) == "aluno-02"
    auth.revogar("aluno-02")
    assert auth.validar_sessao(cookie, chave) == "aluno-02", "a assinatura continua boa"
    assert auth.participante_da_sessao(cookie, chave) is None


def test_zerar_expulsa_quem_estava_dentro(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(2)
    chave = auth.segredo()
    cookie = auth.criar_sessao("aluno-01", chave)
    auth.zerar_participantes()
    assert auth.participante_da_sessao(cookie, chave) is None


def test_rotulo_recriado_nao_herda_a_sessao_do_anterior(tmp_path, monkeypatch):
    """Sem isto, as buscas de uma pessoa ficavam no registo de outra.

    O rotulo volta a existir depois de um `--zerar --criar`, mas e outra pessoa
    com outro codigo: o cookie antigo nao pode continuar a servir. Quem garante
    isso e a troca do segredo de assinatura, nao a lista de rotulos.
    """
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    antiga = auth.criar_sessao("aluno-01", auth.segredo())
    auth.zerar_participantes()
    (tmp_path / "s.txt").write_bytes(b"outro-segredo-de-32-bytes-ou-mais")
    auth.criar_participantes(1)
    assert auth.participante_da_sessao(antiga, auth.segredo()) is None


def test_sessao_malformada_continua_a_ser_recusada(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    assert auth.participante_da_sessao("lixo", auth.segredo()) is None


def test_rotulos_ativos_ve_o_ficheiro_mudar(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert auth.rotulos_ativos() == frozenset()
    auth.criar_participantes(2)
    assert auth.rotulos_ativos() == {"aluno-01", "aluno-02"}
    auth.revogar("aluno-01")
    assert auth.rotulos_ativos() == {"aluno-02"}


def test_novo_codigo_troca_o_codigo_e_mantem_o_rotulo(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    antigo = next(iter(auth.criar_participantes(1)))
    novo = auth.novo_codigo("aluno-01")
    assert novo and novo != antigo
    assert auth.participante_do_codigo(antigo) is None
    assert auth.participante_do_codigo(novo) == "aluno-01"


def test_novo_codigo_expulsa_a_sessao_aberta(tmp_path, monkeypatch):
    """O motivo para trocar um codigo e muitas vezes que ele andou por onde nao
    devia - e nesse caso quem o usou tem de sair, nao ficar dentro 30 dias."""
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    chave = auth.segredo()
    cookie = auth.criar_sessao("aluno-01", chave)
    assert auth.participante_da_sessao(cookie, chave) == "aluno-01"
    auth.novo_codigo("aluno-01")
    assert auth.participante_da_sessao(cookie, chave) is None
    # Quem entra com o codigo novo recebe uma sessao da epoca nova, e essa vale.
    assert auth.participante_da_sessao(auth.criar_sessao("aluno-01", chave), chave) == "aluno-01"


def test_novo_codigo_de_quem_nao_existe(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    assert auth.novo_codigo("aluno-99") is None


def test_zerar_e_recriar_nao_herda_a_sessao(tmp_path, monkeypatch):
    """Sem o corte por epoca isto obrigava a trocar o segredo da maquina a mao."""
    _isolar(tmp_path, monkeypatch)
    auth.criar_participantes(1)
    chave = auth.segredo()
    antiga = auth.criar_sessao("aluno-01", chave)
    auth.zerar_participantes()
    auth.criar_participantes(1)
    assert "aluno-01" in auth.rotulos_ativos()
    assert auth.participante_da_sessao(antiga, chave) is None


def test_simbolo_csrf_e_estavel_e_por_participante(tmp_path, monkeypatch):
    _isolar(tmp_path, monkeypatch)
    um = auth.simbolo_csrf("admin-01")
    assert um == auth.simbolo_csrf("admin-01")
    assert um != auth.simbolo_csrf("aluno-01")
    assert auth.csrf_valido("admin-01", um)
    assert not auth.csrf_valido("aluno-01", um)
    assert not auth.csrf_valido("admin-01", "x" * 32)
    assert not auth.csrf_valido(None, um)
    assert not auth.csrf_valido("admin-01", None)
