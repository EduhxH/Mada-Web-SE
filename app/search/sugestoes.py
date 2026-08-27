from dataclasses import dataclass

ORIGEM_HISTORICO = "historico"
ORIGEM_POPULAR = "popular"
ORIGEM_VOCABULARIO = "vocabulario"

MINIMO_PARTICIPANTES = 2
COMPRIMENTO_MINIMO = 2
LIMITE_PADRAO = 8


@dataclass(frozen=True)
class Sugestao:
    texto: str
    origem: str


def escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def historico(conexao_uso, participante: str, prefixo: str, limite: int):
    padrao = escapar_like(prefixo.lower()) + "%"
    linhas = conexao_uso.execute(
        "SELECT consulta, MAX(momento) FROM eventos"
        " WHERE tipo = 'busca' AND participante = ?"
        " AND resultados > 0 AND LOWER(consulta) LIKE ? ESCAPE '\\'"
        " GROUP BY LOWER(consulta) ORDER BY 2 DESC LIMIT ?",
        (participante, padrao, limite),
    ).fetchall()
    return [linha[0] for linha in linhas]


def populares(conexao_uso, prefixo: str, limite: int):
    padrao = escapar_like(prefixo.lower()) + "%"
    linhas = conexao_uso.execute(
        "SELECT consulta, COUNT(*) FROM eventos"
        " WHERE tipo = 'busca' AND resultados > 0 AND LOWER(consulta) LIKE ? ESCAPE '\\'"
        " GROUP BY LOWER(consulta)"
        " HAVING COUNT(DISTINCT participante) >= ?"
        " ORDER BY 2 DESC LIMIT ?",
        (padrao, MINIMO_PARTICIPANTES, limite),
    ).fetchall()
    return [linha[0] for linha in linhas]


def vocabulario(conexao_indice, prefixo: str, limite: int):
    padrao = escapar_like(prefixo.lower()) + "%"
    linhas = conexao_indice.execute(
        "SELECT t.termo, COUNT(p.doc_id) FROM terms t"
        " JOIN postings p ON p.term_id = t.id"
        " WHERE t.termo LIKE ? ESCAPE '\\'"
        " GROUP BY t.id ORDER BY 2 DESC LIMIT ?",
        (padrao, limite),
    ).fetchall()
    return [linha[0] for linha in linhas]


def sugerir(
    conexao_uso,
    conexao_indice,
    participante: str,
    prefixo: str,
    limite: int = LIMITE_PADRAO,
) -> list[Sugestao]:
    prefixo = prefixo.strip()
    if len(prefixo) < COMPRIMENTO_MINIMO:
        return []

    encontradas: list[Sugestao] = []
    vistos: set[str] = set()

    def juntar(textos, origem):
        for texto in textos:
            chave = texto.lower().strip()
            if not chave or chave in vistos or chave == prefixo.lower():
                continue
            vistos.add(chave)
            encontradas.append(Sugestao(texto, origem))
            if len(encontradas) >= limite:
                return True
        return False

    if juntar(historico(conexao_uso, participante, prefixo, limite), ORIGEM_HISTORICO):
        return encontradas
    if juntar(populares(conexao_uso, prefixo, limite), ORIGEM_POPULAR):
        return encontradas

    # a ultima palavra e a que o utilizador esta a escrever
    palavras = prefixo.split()
    parcial = palavras[-1]
    anteriores = " ".join(palavras[:-1])
    for termo in vocabulario(conexao_indice, parcial, limite):
        completa = f"{anteriores} {termo}".strip()
        if juntar([completa], ORIGEM_VOCABULARIO):
            break
    return encontradas
