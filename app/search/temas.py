"""Extracao de temas caracteristicos de uma disciplina.

IMPORTANTE: as listas aqui sao stop words *de tema*, nao de indexacao. Um
aluno tem de continuar a poder pesquisar "criterios de avaliacao" ou
"planificacao modular" - essas palavras continuam no indice e continuam a ser
pesquisaveis. O que estas listas impedem e que aparecam como SUGESTAO de tema,
onde nao ajudam ninguem a descobrir conteudo.
"""

import math

from app.indexing import pos, storage
from app.indexing.tokenizer import remover_acentos, tokenizar

LIMITE_TEMAS = 18
MINIMO_DOCUMENTOS_TEMA = 3
COBERTURA_MAXIMA = 0.5
COMPRIMENTO_MINIMO_TEMA = 4
COMPRIMENTO_MAXIMO_TEMA = 16
LIFT_MINIMO = 1.6
MINIMO_DOCUMENTOS_CONTEUDO = 8
# Um tema que aparece em muitas disciplinas nao distingue nenhuma delas.
ESPALHAMENTO_MAXIMO = 1 / 3

# Vocabulario de documentos curriculares e administrativos: aparece em todas
# as disciplinas e nao distingue conteudo nenhum.
TERMOS_NAO_TEMATICOS = frozenset(
    """
    dominio dominios competencia competencias aprendizagem aprendizagens
    objetivo objetivos conteudo conteudos atividade atividades situacao
    situacoes estrategia estrategias recurso recursos metodologia metodologias
    instrumento instrumentos descritor descritores indicador indicadores
    parametro parametros criterio criterios ponderacao ponderacoes avaliacao
    avaliacoes modulo modulos modular planificacao planificacoes unidade
    unidades sumario sumarios licao licoes aula aulas tempo tempos carga
    horaria letivo letivos periodo periodos semestre semestres trimestre
    disciplina disciplinas curso cursos turma turmas aluno alunos professor
    professores docente docentes formador formadores formando formandos
    escola escolar ensino educacao educativo educativa formacao pedagogico
    pedagogica curricular curriculares programa programas referencial
    referenciais perfil perfis saida saidas nivel niveis grau graus etapa
    etapas fase fases meta metas
    trabalho trabalhos exercicio exercicios ficha fichas teste testes
    exemplo exemplos forma formas modo modos tipo tipos caso casos parte
    partes conjunto conjuntos grupo grupos elemento elementos aspeto aspetos
    aspecto aspectos questao questoes tema temas topico topicos ponto pontos
    processo processos sistema sistemas modelo modelos metodo metodos
    autonomia responsabilidade cidadania cooperacao colaboracao participacao
    conhecimento conhecimentos capacidade capacidades atitude atitudes
    valor valores saber saberes pratica praticas teoria teorias
    documento documentos manual manuais material materiais apoio suporte
    total geral especifico especifica generico generica diverso diversos
    varios varias diferente diferentes proprio propria mesmo mesma
    muito muita muitos muitas pouco pouca poucos poucas todo toda todos todas
    outro outra outros outras algum alguma alguns algumas cada qualquer
    entao assim ainda apenas tambem talvez porque porem contudo todavia
    alem depois antes durante enquanto quando onde como quanto
    grande grandes pequeno pequena pequenos pequenas alto alta altos altas
    baixo baixa novo nova novos novas velho antigo simples complexo
    bom boa bons boas melhor pior otimo otima otimos otimas
    real reais individual individuais coletivo coletiva principal principais
    seguinte seguintes anterior anteriores proximo proxima primeiro primeira
    segundo segunda terceiro ultimo ultima
    eram foram sendo estando havendo
    verdade fato facto figura figuras tabela tabelas quadro quadros anexo
    nota notas menor maior menores maiores vazio vazia cheio cheia
    aberto aberta fechado fechada percentagem percentagens percentual
    explicacao explicacoes funcionalidade funcionalidades caracteristica
    caracteristicas vantagem vantagens desvantagem desvantagens
    objetivo finalidade utilizacao aplicacao aplicacoes
    construcao representacao representacoes decisao decisoes analise analises
    """.split()
)

# Palavras funcionais inglesas: material de Ingles e manuais de software estao
# cheios delas e nao sao temas.
TERMOS_INGLESES = frozenset(
    """
    the and for you your are was were will would can could should must have
    has had been being does did done not but with from this that these those
    they them their there here what when where which while who whom whose
    how why all any some each every both few more most other another such
    only own same than too very just also then than into over under about
    after before between during through above below off out again once
    make made take taken give given get got put set use used using
    new old good bad best worst first last next same right left
    one two three four five six seven eight nine ten
    page slide chapter section part example note table figure
    main click open close save file text word line list item
    """.split()
)

# Palavras-chave e identificadores de codigo: aparecem em material de
# programacao mas nao sao materia de estudo.
TERMOS_CODIGO = frozenset(
    """
    return void null true false int char bool byte long float double var let
    const public private static class struct enum namespace using import
    from def self this new delete throw catch try finally break continue
    else elif endif then begin end print println console log
    conn cmd req res args kwargs argv init main tmp temp aux obj val
    src dst ptr len idx num str num_ id_ pk fk sql select insert update
    where order group join inner outer left right union query queries
    dataset datatable datagrid textbox label button click_ event handler
    form_ forms_ params param async await yield lambda
    """.split()
)

# Titulos que denunciam documento administrativo, nao de conteudo
# Ficheiros de codigo-fonte: o vocabulario e de identificadores, nao de
# materia de estudo (txtnome, namespace, conn...).
EXTENSOES_NAO_TEMATICAS = (".cs", ".designer", ".resx", ".config")

PADROES_ADMINISTRATIVOS = (
    "planificacao",
    "planif",
    "criterios",
    "justificacao",
    "agenda",
    "dossier",
    "sumario",
    "matriz",
    "regulamento",
    "ata",
)

RUIDO_TECNICO = frozenset(
    """
    wp uploads content http https www pdf doc docx pptx html php index
    page site com net org file files cdn img jpg png designer form
    pagina paginas slide slides ficheiro ficheiros anexo anexos
    """.split()
)


def e_forma_verbal(termo: str, vocabulario: set[str]) -> bool:
    """Deteta 3a pessoa do singular usando o proprio corpus.

    "aumenta" e verbo se "aumentar" existir no vocabulario. Nomes como "onda",
    "amostra" ou "geometria" nao tem infinitivo correspondente, e passam.
    """
    if len(termo) < 5 or termo[-1] not in "ae":
        return False
    candidatos = (termo + "r", termo[:-1] + "er", termo[:-1] + "ir")
    return any(candidato in vocabulario for candidato in candidatos)


def _e_candidato(termo: str, proprios: set[str]) -> bool:
    if not COMPRIMENTO_MINIMO_TEMA <= len(termo) <= COMPRIMENTO_MAXIMO_TEMA:
        return False
    if termo.isdigit():
        return False
    if any(c.isdigit() for c in termo):
        return False
    if termo in proprios or termo in RUIDO_TECNICO:
        return False
    if termo in TERMOS_NAO_TEMATICOS or termo in TERMOS_INGLESES:
        return False
    if termo in TERMOS_CODIGO:
        return False
    return pos.serve_como_tema(termo)


def _lift(df_disc: int, n_disc: int, df_total: int, total: int) -> float:
    df_resto = max(df_total - df_disc, 0)
    n_resto = max(total - n_disc, 1)
    taxa_disc = df_disc / n_disc
    taxa_resto = (df_resto + 0.5) / (n_resto + 1)
    return taxa_disc / taxa_resto


_cache_espalhamento: dict[int, dict[str, int]] = {}


def _espalhamento(conexao_indice, total_docs: int) -> tuple[dict[str, int], int]:
    if total_docs not in _cache_espalhamento:
        _cache_espalhamento.clear()
        _cache_espalhamento[total_docs] = storage.disciplinas_por_termo(
            conexao_indice
        )
    return _cache_espalhamento[total_docs], storage.contar_disciplinas(conexao_indice)


def limpar_cache() -> None:
    _cache_espalhamento.clear()


def extrair(
    conexao_indice, disciplina: str, limite: int = LIMITE_TEMAS
) -> list[str]:
    total = storage.contar_documentos(conexao_indice)
    n_disc = storage.contar_por_disciplina(conexao_indice, disciplina)
    if not n_disc or not total:
        return []

    # Excluir documentos administrativos so compensa se sobrarem documentos
    # de conteudo suficientes; caso contrario a amostra fica pequena demais.
    n_conteudo = storage.contar_por_disciplina(
        conexao_indice, disciplina, apenas_conteudo=True
    )
    usar_conteudo = n_conteudo >= MINIMO_DOCUMENTOS_CONTEUDO
    if not usar_conteudo:
        n_conteudo = n_disc
    contagens = storage.df_na_disciplina(
        conexao_indice,
        disciplina,
        MINIMO_DOCUMENTOS_TEMA,
        excluir_administrativos=usar_conteudo,
    )
    if not contagens:
        return []

    proprios = set(tokenizar(disciplina, remover_stop_words=False))
    proprios |= {remover_acentos(disciplina.lower())}

    espalhamento, n_disciplinas = _espalhamento(conexao_indice, total)
    vocabulario = set(espalhamento)
    teto_espalhamento = max(1, int(n_disciplinas * ESPALHAMENTO_MAXIMO))

    pontuados = []
    for termo, df_disc, df_total in contagens:
        if not _e_candidato(termo, proprios):
            continue
        if espalhamento.get(termo, 1) > teto_espalhamento:
            continue
        if e_forma_verbal(termo, vocabulario):
            continue
        cobertura = df_disc / n_conteudo
        if cobertura > COBERTURA_MAXIMA:
            continue
        lift = _lift(df_disc, n_conteudo, df_total, total)
        if lift < LIFT_MINIMO:
            continue
        pontuados.append((cobertura * math.log(lift), termo))

    pontuados.sort(reverse=True)
    return [termo for _, termo in pontuados[:limite]]
