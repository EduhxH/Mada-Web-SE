from app.indexing.tokenizer import tokenizar


def gerar_trecho(texto: str, termos: set[str], raio: int = 12) -> str:
    palavras = texto.split()
    alvo = 0
    for i, palavra in enumerate(palavras):
        normalizada = tokenizar(palavra, remover_stop_words=False)
        if normalizada and normalizada[0] in termos:
            alvo = i
            break
    inicio = max(0, alvo - raio)
    fim = min(len(palavras), alvo + raio + 1)
    trecho = " ".join(palavras[inicio:fim])
    prefixo = "..." if inicio > 0 else ""
    sufixo = "..." if fim < len(palavras) else ""
    return prefixo + trecho + sufixo
