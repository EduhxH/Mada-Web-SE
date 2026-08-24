COMPRIMENTO_MINIMO_SUGESTAO = 4
DISTANCIA_MAXIMA = 2


def distancia_edicao(a: str, b: str, limite: int = DISTANCIA_MAXIMA) -> int:
    if abs(len(a) - len(b)) > limite:
        return limite + 1
    if not a:
        return len(b)
    if not b:
        return len(a)

    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, start=1):
        atual = [i]
        for j, letra_b in enumerate(b, start=1):
            custo = 0 if letra_a == letra_b else 1
            atual.append(
                min(
                    anterior[j] + 1,
                    atual[j - 1] + 1,
                    anterior[j - 1] + custo,
                )
            )
        if min(atual) > limite:
            return limite + 1
        anterior = atual
    return anterior[-1]


def sugerir(
    termo: str,
    vocabulario: list[tuple[str, int]],
    limite: int = DISTANCIA_MAXIMA,
) -> str | None:
    if len(termo) < COMPRIMENTO_MINIMO_SUGESTAO:
        return None
    melhor: str | None = None
    melhor_distancia = limite + 1
    melhor_df = -1
    for candidato, df in vocabulario:
        if candidato == termo:
            return None
        distancia = distancia_edicao(termo, candidato, limite)
        if distancia > limite:
            continue
        if distancia < melhor_distancia or (
            distancia == melhor_distancia and df > melhor_df
        ):
            melhor, melhor_distancia, melhor_df = candidato, distancia, df
    return melhor
