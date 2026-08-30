"""Calao da escola: o aluno diz "ficha", o documento chama-se "Guiao".

Isto e diferente da expansao morfologica, que troca formas da mesma palavra.
Aqui trocam-se palavras diferentes que a escola usa para a mesma coisa, e por
isso a regra tem de ser mais desconfiada.

Porque escrito a mao e nao aprendido: medido, o modelo de embeddings poe
"ficha da materia de portugues" a 0.4563 do guiao certo e a 0.4221 de um
distrator - tres centesimas nao decidem nada. Num dominio fechado, vinte
sinonimos escritos por quem conhece a escola batem um modelo geral, e ao
contrario dele podem ser lidos e corrigidos.

O teto de frequencia e a defesa contra a inundacao: "trabalho" aparece em 551
dos 1761 documentos, e deixar "ficha" (37) alcanca-lo trocava uma resposta
precisa por meio corpus.
"""

# Grupos de termos que a escola usa como equivalentes. Todos os membros de um
# grupo expandem uns para os outros.
GRUPOS = (
    ("ficha", "fichas", "guiao", "guioes", "exercicio", "exercicios"),
    ("sebenta", "sebentas", "manual", "manuais", "apontamentos"),
    ("teste", "testes", "prova", "provas", "exame", "exames"),
    ("materia", "conteudo", "conteudos", "planificacao"),
    ("horario", "horarios", "calendario", "calendarios"),
)

# Um sinonimo em mais de 10% da colecao nao distingue nada: acrescenta-lo so
# dilui. Fracao e nao numero absoluto, para continuar a valer quando o corpus
# crescer em setembro.
TETO_FREQUENCIA = 0.10
MAXIMO_SINONIMOS = 3


def _indice() -> dict[str, tuple[str, ...]]:
    mapa: dict[str, tuple[str, ...]] = {}
    for grupo in GRUPOS:
        for termo in grupo:
            mapa[termo] = grupo
    return mapa


_MAPA = _indice()


def relacionados(
    termo: str,
    frequencias: dict[str, int],
    total_documentos: int,
    teto: float = TETO_FREQUENCIA,
) -> set[str]:
    """Sinonimos do termo que existem no indice e nao sao comuns demais.

    `frequencias` e {termo: em quantos documentos aparece}.
    """
    grupo = _MAPA.get(termo)
    if not grupo or not total_documentos:
        return set()

    limite = total_documentos * teto
    encontrados = []
    for candidato in grupo:
        if candidato == termo:
            continue
        quantos = frequencias.get(candidato, 0)
        if 0 < quantos <= limite:
            encontrados.append((quantos, candidato))

    # Os mais raros primeiro: sao os que mais distinguem.
    encontrados.sort()
    return {candidato for _, candidato in encontrados[:MAXIMO_SINONIMOS]}


def expandir(
    termos: set[str], frequencias: dict[str, int], total_documentos: int
) -> dict[str, set[str]]:
    return {
        termo: relacionados(termo, frequencias, total_documentos)
        for termo in termos
    }
