"""Expansao morfologica da consulta (numero: singular <-> plural).

Principio: as regras geram candidatos, o vocabulario decide quais sao reais.
Nenhuma variante entra sem existir no indice, por isso e impossivel expandir
para palavras inventadas.

Ao contrario do stemming, isto nao toca no indice: o termo continua guardado
tal como aparece nos documentos, e e a pergunta que fica mais generosa.
"""

COMPRIMENTO_MINIMO = 3
MAXIMO_VARIANTES = 3


def _plurais(termo: str) -> list[str]:
    if termo.endswith("ao"):
        return [termo[:-2] + "oes", termo[:-2] + "aos", termo[:-2] + "aes"]
    if termo.endswith("l"):
        return [termo[:-1] + "is"]
    if termo.endswith("m"):
        return [termo[:-1] + "ns"]
    if termo.endswith(("r", "z", "s")):
        return [termo + "es"]
    return [termo + "s"]


def _singulares(termo: str) -> list[str]:
    candidatos = []
    if termo.endswith("oes"):
        candidatos.append(termo[:-3] + "ao")
    if termo.endswith("aes"):
        candidatos.append(termo[:-3] + "ao")
    if termo.endswith("aos"):
        candidatos.append(termo[:-1])
    if termo.endswith("is"):
        candidatos.append(termo[:-2] + "l")
    if termo.endswith("ns"):
        candidatos.append(termo[:-2] + "m")
    if termo.endswith("es"):
        candidatos.append(termo[:-2])
    if termo.endswith("s"):
        candidatos.append(termo[:-1])
    return candidatos


def variantes(termo: str, vocabulario: set[str]) -> set[str]:
    """Formas do mesmo termo que existem no indice, incluindo a original."""
    encontradas = {termo}
    if len(termo) < COMPRIMENTO_MINIMO:
        return encontradas

    for candidato in _plurais(termo) + _singulares(termo):
        if len(candidato) < COMPRIMENTO_MINIMO or candidato == termo:
            continue
        if candidato in vocabulario:
            encontradas.add(candidato)
        if len(encontradas) >= MAXIMO_VARIANTES:
            break
    return encontradas


def expandir(termos: set[str], vocabulario: set[str]) -> dict[str, set[str]]:
    return {termo: variantes(termo, vocabulario) for termo in termos}
