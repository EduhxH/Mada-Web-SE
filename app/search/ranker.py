import math


def pontuar(
    postings_por_termo: dict[str, dict[int, int]],
    candidatos: set[int],
    tamanhos: dict[int, int],
    total_docs: int,
) -> list[tuple[int, float]]:
    pontuacoes: list[tuple[int, float]] = []
    for doc_id in candidatos:
        pontos = 0.0
        for postings in postings_por_termo.values():
            freq = postings.get(doc_id)
            if freq is None:
                continue
            tf = freq / tamanhos[doc_id]
            idf = math.log(total_docs / len(postings))
            pontos += tf * idf
        pontuacoes.append((doc_id, pontos))
    pontuacoes.sort(key=lambda par: par[1], reverse=True)
    return pontuacoes
