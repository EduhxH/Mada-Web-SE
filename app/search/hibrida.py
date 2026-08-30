"""Junta a busca lexical com a semantica.

O problema de juntar duas listas e que as pontuacoes nao sao comparaveis: o
TF-IDF desta colecao anda entre 0.01 e 0.3 e varia duas ordens de grandeza
conforme a consulta, enquanto o cosseno vive entre -1 e 1 e e estavel. Somar
as duas com pesos exige normalizar, e qualquer normalizacao por consulta faz
o mesmo documento valer coisas diferentes conforme a companhia que tem.

Por isso a fusao e por POSICAO e nao por pontuacao (Reciprocal Rank Fusion):
cada lista contribui 1/(K + posicao). Nao precisa de escala nem de
calibracao, e um documento que as duas listas poem la em cima sobe acima de
um que so uma delas viu.

O risco do RRF e ignorar a magnitude: se a busca semantica nao tiver nada de
bom, o seu primeiro resultado - por mau que seja - continua a receber o
credito de primeiro lugar. Dai o piso de semelhanca: abaixo dele o resultado
nem entra na lista.
"""

from dataclasses import dataclass, field

from app.indexing import storage
from app.search import agrupamento, intencao
from app.search.query import buscar_detalhado

# Constante classica do RRF. Alta o suficiente para que a diferenca entre o
# 1o e o 2o lugar nao esmague o resto da lista.
K_FUSAO = 60
# Abaixo disto a semelhanca e ruido. Medido: uma parafrase certa fica acima
# de 0.5, um documento sem relacao fica perto de 0.2.
PISO_SEMELHANCA = 0.45
# Quantos documentos a busca semantica traz para a fusao.
LIMITE_SEMANTICO = 40
# Balde dos documentos rastreados do site, que servem qualquer disciplina.
DISCIPLINA_GERAL = "Escola"



@dataclass
class Fusao:
    documentos: list = field(default_factory=list)
    so_lexical: int = 0
    so_semantico: int = 0
    em_ambas: int = 0

    @property
    def usou_semantica(self) -> bool:
        return bool(self.so_semantico or self.em_ambas)


def _posicoes(ids: list[int]) -> dict[int, int]:
    return {doc_id: posicao for posicao, doc_id in enumerate(ids, start=1)}


def fundir(
    lexicais: list[tuple[int, float]],
    semanticos: dict[int, float],
    piso: float = PISO_SEMELHANCA,
    k: int = K_FUSAO,
) -> Fusao:
    """Junta as duas listas por posicao e devolve (doc_id, pontuacao) ordenado.

    `lexicais` vem ja ordenada por relevancia; `semanticos` e
    {doc_id: semelhanca}, filtrada aqui pelo piso.
    """
    ordem_lexical = _posicoes([doc_id for doc_id, _ in lexicais])
    acima_do_piso = {
        doc_id: valor for doc_id, valor in semanticos.items() if valor >= piso
    }
    ordem_semantica = _posicoes(
        sorted(acima_do_piso, key=lambda d: -acima_do_piso[d])
    )

    pontuacoes: dict[int, float] = {}
    for ordem in (ordem_lexical, ordem_semantica):
        for doc_id, posicao in ordem.items():
            pontuacoes[doc_id] = pontuacoes.get(doc_id, 0.0) + 1.0 / (k + posicao)

    resultado = Fusao(
        documentos=sorted(pontuacoes.items(), key=lambda par: -par[1]),
        so_lexical=len(ordem_lexical.keys() - ordem_semantica.keys()),
        so_semantico=len(ordem_semantica.keys() - ordem_lexical.keys()),
        em_ambas=len(ordem_lexical.keys() & ordem_semantica.keys()),
    )
    return resultado


def buscar(
    conexao,
    consulta: str,
    matriz=None,
    disciplina: str | None = None,
    piso: float = PISO_SEMELHANCA,
    agrupar: bool = True,
    permitir_ou: bool = True,
):
    """Resultado lexical enriquecido com o que a semantica encontrou.

    Devolve o mesmo ResultadoBusca da busca lexical, com a lista de
    documentos reordenada pela fusao. Manter o mesmo tipo e de proposito: a
    interface, as sugestoes de correcao e as estatisticas continuam a
    funcionar sem saber que isto existe.

    Sem indice semantico (matriz vazia), degrada para busca lexical pura.
    """
    recente = intencao.pede_recente(consulta)
    if recente:
        # "ultima" e "mais recente" pedem ordenacao, nao sao termos de busca:
        # deixa-las na consulta puxava documentos que falam de novidades.
        sem_marcas = intencao.limpar_recencia(consulta)
        if sem_marcas.strip():
            consulta = sem_marcas

    detetada = ""
    if disciplina is None:
        detetada, restante = intencao.detetar_disciplina(
            consulta, storage.listar_disciplinas(conexao)
        )
        if detetada:
            # "Escola" nao e uma disciplina, e o que foi rastreado do site:
            # regulamentos, calendarios, criterios. Um aluno que pergunta por
            # TIC pode muito bem querer os criterios de avaliacao de TIC, que
            # vivem la e nao no Moodle.
            alvo = [detetada, DISCIPLINA_GERAL]
            candidatos = buscar_detalhado(
                conexao, restante, alvo, permitir_ou=permitir_ou
            )
            # So vale a pena filtrar se sobrar alguma coisa: um filtro que
            # esvazia a pagina e pior que nao ter filtro nenhum.
            if candidatos.documentos:
                disciplina, consulta = alvo, restante
            else:
                detetada = ""

    resultado = buscar_detalhado(
        conexao, consulta, disciplina, permitir_ou=permitir_ou
    )
    resultado.disciplina_detetada = detetada

    if matriz is not None and len(matriz):
        resultado = _juntar_semantica(
            conexao, consulta, resultado, matriz, disciplina, piso
        )
    if detetada:
        resultado.documentos = realcar_disciplina(
            resultado.documentos, detetada
        )

    if recente:
        resultado.documentos = ordenar_por_data(resultado.documentos)
        resultado.ordenado_por_recencia = True

    # Agrupar e o ultimo passo: depois de ordenar, para que a pagina que
    # lidera cada ficheiro seja mesmo a melhor pela ordem final.
    if agrupar:
        resultado.grupos = agrupamento.agrupar_por_ficheiro(resultado.documentos)
        resultado.documentos = agrupamento.achatar(resultado.grupos)
    return resultado


def realcar_disciplina(documentos: list, disciplina: str) -> list:
    """Poe a disciplina nomeada a frente dos documentos gerais da escola.

    E uma particao e nao um multiplicador de propósito. Comecei por reforcar
    a pontuacao e varri o fator contra avaliacao/consultas.json: o ganho
    crescia ate 50 e ai parava, porque a partir dai qualquer documento da
    disciplina ja passava a frente de qualquer documento da escola. Ou seja,
    o que estava a ser medido era uma particao com um numero magico pelo
    meio. Escrita como particao, faz-se o mesmo e le-se melhor.

    Os documentos da escola nao saem da lista - as vezes sao mesmo a
    resposta, como os criterios de avaliacao de TIC, que vivem no site e nao
    no Moodle. Deixam apenas de ganhar por serem 57% da colecao.

    A ordem relativa dentro de cada metade e a que vinha do ranqueamento.
    """
    if not disciplina:
        return documentos
    da_disciplina = [par for par in documentos if par[0].disciplina == disciplina]
    restantes = [par for par in documentos if par[0].disciplina != disciplina]
    return da_disciplina + restantes


def ordenar_por_data(documentos: list) -> list:
    """Mais recentes primeiro, mantendo a ordem de relevancia nos empates.

    Documentos sem data ficam no fim e nao a frente: sem data nao ha como
    afirmar que sao recentes, e empurra-los para cima seria inventar.
    """
    com_data = [par for par in documentos if par[0].data]
    sem_data = [par for par in documentos if not par[0].data]
    com_data.sort(key=lambda par: par[0].data, reverse=True)
    return com_data + sem_data


def _juntar_semantica(conexao, consulta, resultado, matriz, disciplina, piso):
    """Importa a parte semantica so quando ha indice semantico para usar.

    Sem isto, `numpy` passava a ser preciso para arrancar o servidor - e a
    busca semantica esta desligada por omissao, por medir pior que a lexical.
    Quem so quer o motor nao deve ter de instalar uma biblioteca numerica.
    """
    from app.search import semantica

    semelhantes = semantica.procurar(matriz, consulta, LIMITE_SEMANTICO)
    if disciplina:
        nomes = [disciplina] if isinstance(disciplina, str) else list(disciplina)
        permitidos = set()
        for nome in nomes:
            permitidos |= storage.carregar_ids_por_disciplina(conexao, nome)
        semelhantes = {d: v for d, v in semelhantes.items() if d in permitidos}

    lexicais = [(doc.id, pontuacao) for doc, pontuacao in resultado.documentos]
    fusao = fundir(lexicais, semelhantes, piso=piso)
    if not fusao.usou_semantica:
        return resultado

    ja_carregados = {doc.id: doc for doc, _ in resultado.documentos}
    em_falta = [d for d, _ in fusao.documentos if d not in ja_carregados]
    if em_falta:
        ja_carregados.update(storage.carregar_documentos(conexao, em_falta))

    resultado.documentos = [
        (ja_carregados[doc_id], pontuacao)
        for doc_id, pontuacao in fusao.documentos
        if doc_id in ja_carregados
    ]
    return resultado
