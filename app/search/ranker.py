import math


def pontuar(
    postings_por_termo: dict[str, dict[int, int]],
    candidatos: set[int],
    tamanhos: dict[int, int],
    total_docs: int,
) -> list[tuple[int, float]]:
    idf_por_termo = {
        termo: math.log(total_docs / len(postings))
        for termo, postings in postings_por_termo.items()
        if postings
    }
    total_termos = len(postings_por_termo)
    pontuacoes: list[tuple[int, float]] = []
    for doc_id in candidatos:
        pontos = 0.0
        encontrados = 0
        for termo, postings in postings_por_termo.items():
            freq = postings.get(doc_id)
            if freq is None:
                continue
            encontrados += 1
            pontos += (freq / tamanhos[doc_id]) * idf_por_termo[termo]
        if total_termos:
            pontos *= encontrados / total_termos
        pontuacoes.append((doc_id, pontos))
    pontuacoes.sort(key=lambda par: par[1], reverse=True)
    return pontuacoes
