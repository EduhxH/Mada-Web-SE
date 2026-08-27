from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.models.document import Documento
from app.search import temas


def _indice(tmp_path, documentos):
    conexao = storage.abrir(tmp_path / "i.sqlite3")
    indice, tamanhos = construir_indice(documentos)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    return conexao


def _colecao():
    docs = []
    conteudos = [
        "a radiacao solar aquece a superficie",
        "radiacao infravermelha e temperatura ambiente",
        "temperatura e transferencia de calor",
        "espectro visivel e comprimento de onda",
        "onda eletromagnetica e espectro continuo",
        "calor especifico e capacidade termica",
        "termodinamica primeira lei sistemas",
        "termodinamica entropia e trabalho util",
        "onda sonora e propagacao no meio",
        "espectro de absorcao e emissao",
    ]
    for n, texto in enumerate(conteudos, start=1):
        docs.append(Documento(n, f"Sebenta modulo {n}", texto, "f.pdf", "Fisica"))
    for n in range(11, 21):
        docs.append(
            Documento(n, f"Outro {n}", "gramatica sintaxe texto literario", "f", "Letras")
        )
    return docs


def test_verbos_de_curriculo_nao_aparecem(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Fisica extra {n}",
                "o aluno deve reconhecer interpretar analisar e propor solucoes"
                " recorrendo a modelos",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    encontrados = temas.extrair(conexao, "Fisica")
    for verbo in ("reconhecer", "interpretar", "analisar", "propor", "recorrendo"):
        assert verbo not in encontrados


def test_temas_reais_aparecem(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    encontrados = temas.extrair(conexao, "Fisica")
    assert {"radiacao", "temperatura", "espectro"} & set(encontrados)


def test_vocabulario_curricular_e_excluido(tmp_path):
    docs = _colecao()
    for n in range(21, 28):
        docs.append(
            Documento(
                n, f"Ficha {n}",
                "dominios competencias objetivos conteudos atividades criterios"
                " avaliacao radiacao",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    encontrados = temas.extrair(conexao, "Fisica")
    for termo in ("dominios", "competencias", "objetivos", "criterios", "avaliacao"):
        assert termo not in encontrados


def test_documentos_administrativos_sao_ignorados(tmp_path):
    docs = _colecao()
    # 10 planificacoes com vocabulario proprio, mas titulo administrativo
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Planificacao Modular {n}",
                "descritor ponderacao trimestre matricula",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    encontrados = temas.extrair(conexao, "Fisica")
    assert "descritor" not in encontrados
    assert "ponderacao" not in encontrados


def test_codigo_fonte_nao_gera_temas(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Formulario{n}", "namespace txtnome conn dataset",
                f"projeto/Form{n}.cs", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    encontrados = temas.extrair(conexao, "Fisica")
    assert "namespace" not in encontrados
    assert "txtnome" not in encontrados


def test_nome_da_disciplina_nao_e_tema(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert "fisica" not in temas.extrair(conexao, "Fisica")


def test_termos_demasiado_longos_ou_com_digitos(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Extra {n}", "manualficheirostextolongodemais parte1 x9 onda",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    encontrados = temas.extrair(conexao, "Fisica")
    assert "manualficheirostextolongodemais" not in encontrados
    assert "parte1" not in encontrados


def test_termo_comum_a_toda_a_colecao_nao_e_tema(tmp_path):
    docs = [
        Documento(n, f"Doc {n}", "generico presente radiacao", "f.pdf", "Fisica")
        for n in range(1, 11)
    ] + [
        Documento(n, f"Outro {n}", "generico presente gramatica", "f", "Letras")
        for n in range(11, 21)
    ]
    conexao = _indice(tmp_path, docs)
    assert "generico" not in temas.extrair(conexao, "Fisica")


def test_disciplina_inexistente(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert temas.extrair(conexao, "Astronomia") == []


def test_respeita_o_limite(tmp_path):
    conexao = _indice(tmp_path, _colecao())
    assert len(temas.extrair(conexao, "Fisica", limite=3)) <= 3


def _colecao_muitas_disciplinas():
    """Um termo comum a todas as disciplinas nao pode ser tema de nenhuma."""
    docs = []
    disciplinas = ["Fisica", "Letras", "Historia", "Musica", "Desporto", "Arte"]
    for indice, nome in enumerate(disciplinas):
        for n in range(4):
            docs.append(
                Documento(
                    len(docs) + 1,
                    f"{nome} {n}",
                    f"generalizado presente aqui {nome.lower()}palavra{n % 2}",
                    "f.pdf",
                    nome,
                )
            )
    return docs


def test_termo_espalhado_por_todas_as_disciplinas_nao_e_tema(tmp_path):
    conexao = _indice(tmp_path, _colecao_muitas_disciplinas())
    temas.limpar_cache()
    for disciplina in ("Fisica", "Letras", "Historia"):
        assert "generalizado" not in temas.extrair(conexao, disciplina)
        assert "presente" not in temas.extrair(conexao, disciplina)


def test_termo_de_uma_so_disciplina_sobrevive(tmp_path):
    docs = _colecao_muitas_disciplinas()
    for n in range(100, 104):
        docs.append(
            Documento(n, f"Fisica extra {n}", "espectroscopia unica aqui", "f.pdf", "Fisica")
        )
    conexao = _indice(tmp_path, docs)
    temas.limpar_cache()
    assert "espectroscopia" in temas.extrair(conexao, "Fisica")


def test_palavras_funcionais_inglesas_fora(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Ingles {n}",
                "you must have your presentations written with the rules",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    temas.limpar_cache()
    encontrados = temas.extrair(conexao, "Fisica")
    for palavra in ("must", "have", "your", "with", "the"):
        assert palavra not in encontrados


def test_adverbios_e_quantificadores_fora(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Extra {n}",
                "muito entao talvez assim simples grande outro cada radiacao",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    temas.limpar_cache()
    encontrados = temas.extrair(conexao, "Fisica")
    for palavra in ("muito", "entao", "talvez", "assim", "simples", "grande", "cada"):
        assert palavra not in encontrados


def test_forma_verbal_detetada_pelo_infinitivo():
    vocabulario = {"aumentar", "utilizar", "permitir", "geometria", "onda"}
    assert temas.e_forma_verbal("aumenta", vocabulario)
    assert temas.e_forma_verbal("utiliza", vocabulario)
    assert temas.e_forma_verbal("permite", vocabulario)


def test_nomes_sem_infinitivo_correspondente_passam():
    vocabulario = {"aumentar", "geometria", "onda", "amostra", "temperatura", "farsa"}
    for nome in ("geometria", "onda", "amostra", "temperatura", "farsa"):
        assert not temas.e_forma_verbal(nome, vocabulario)


def test_forma_verbal_exige_terminacao_em_a_ou_e():
    assert not temas.e_forma_verbal("radiacao", {"radiacaor"})
    assert not temas.e_forma_verbal("calor", {"calorr"})


def test_palavras_de_codigo_fora(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Codigo {n}", "return void null public static conn query radiacao",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    temas.limpar_cache()
    encontrados = temas.extrair(conexao, "Fisica")
    for palavra in ("return", "void", "null", "public", "static", "conn", "query"):
        assert palavra not in encontrados


def test_comparativos_e_adjetivos_fora(tmp_path):
    docs = _colecao()
    for n in range(21, 31):
        docs.append(
            Documento(
                n, f"Extra {n}", "menor maior vazio cheio percentagens figura onda",
                "f.pdf", "Fisica",
            )
        )
    conexao = _indice(tmp_path, docs)
    temas.limpar_cache()
    encontrados = temas.extrair(conexao, "Fisica")
    for palavra in ("menor", "maior", "vazio", "cheio", "percentagens", "figura"):
        assert palavra not in encontrados
