"""Siglas da escola e o que elas querem dizer.

Medido no corpus: PAP aparece em 129 documentos e "prova de aptidao" em 37;
FCT em 63 e "formacao em contexto" em 86. Sao documentos DIFERENTES - cada
autor escolheu uma forma - e quem procura por uma perde a outra. "Formacao em
contexto de trabalho" ficava em 21o lugar, e "trabalho para casa" nao
encontrava nada, porque o documento diz "TPC".

Isto nao e a mesma coisa que os sinonimos. Ali trocam-se palavras por
palavras; aqui uma palavra vale uma EXPRESSAO inteira, e por isso a expansao
tem de ser feita com cuidado:

    postings do conceito = documentos com a sigla
                         U documentos com TODAS as palavras da expressao

A intersecao e o que impede o disparate. "Trabalho para casa" tem "trabalho",
que esta em 554 documentos; procurar por qualquer das palavras trazia meio
corpus. Exigi-las todas juntas devolve o punhado que fala mesmo do assunto.
"""

from app.indexing.tokenizer import tokenizar

# sigla -> por extenso. As duas formas sao tokenizadas com as mesmas regras
# do indice, portanto acentos e palavras vazias tratam-se sozinhos.
SIGLAS = {
    "pap": "prova de aptidao profissional",
    "fct": "formacao em contexto de trabalho",
    "tpc": "trabalho para casa",
    "psi": "tecnico de gestao e programacao de sistemas informaticos",
    "ri": "regulamento interno",
    "paa": "plano anual de atividades",
    "ee": "encarregado de educacao",
    "cp": "conselho pedagogico",
}


def _expansoes() -> dict[str, tuple[str, ...]]:
    return {sigla: tuple(tokenizar(texto)) for sigla, texto in SIGLAS.items()}


_EXPANSOES = _expansoes()


def detetar(termos: set[str]) -> list[tuple[str, tuple[str, ...], set[str]]]:
    """Conceitos presentes na consulta.

    Devolve (sigla, palavras da expansao, termos da consulta que o conceito
    consome). Um conceito e reconhecido pela sigla ou pela expressao completa;
    meia expressao nao conta, senao "trabalho" sozinho virava TPC.
    """
    encontrados = []
    for sigla, palavras in _EXPANSOES.items():
        if sigla in termos:
            encontrados.append((sigla, palavras, {sigla}))
        elif palavras and set(palavras) <= termos:
            encontrados.append((sigla, palavras, set(palavras)))
    return encontrados
