"""Mede a qualidade da busca contra um conjunto de consultas conhecidas.

Existe porque ate aqui a busca era julgada por anedota - olhava-se para uma
consulta, achava-se o resultado mau, mexia-se num peso. Sem uma medida, nao
ha forma de saber se uma mudanca melhorou o conjunto ou se apenas arranjou o
exemplo que estava a ser observado.

As consultas vem do registo de uso real. A verdade-terreno e um pedaco da
origem do documento certo, e nao o seu id: as origens sobrevivem a
reindexacoes.

Uso:
    python scripts/avaliar_busca.py
    python scripts/avaliar_busca.py --detalhe
    python scripts/avaliar_busca.py --guardar base.json
    python scripts/avaliar_busca.py --comparar base.json
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.indexing import storage  # noqa: E402
from app.search.query import buscar_detalhado  # noqa: E402

CONSULTAS = RAIZ / "avaliacao" / "consultas.json"
BANCO = RAIZ / "data" / "indice.sqlite3"
PROFUNDIDADES = (1, 3, 10)
SEM_POSICAO = 0


def posicao_do_esperado(resultados, esperado: str) -> int:
    """Posicao (1-based) do primeiro documento certo; 0 se nao aparecer."""
    alvo = esperado.lower()
    for posicao, (doc, _) in enumerate(resultados, start=1):
        if alvo in doc.origem.lower():
            return posicao
    return SEM_POSICAO


def avaliar(conexao, casos: list[dict], matriz=None, piso=None) -> dict:
    """Com `matriz` avalia a busca hibrida; sem ela, so a lexical."""
    if matriz is not None:
        from app.search import hibrida

        def procurar(consulta):
            return hibrida.buscar(
                conexao, consulta, matriz,
                piso=hibrida.PISO_SEMELHANCA if piso is None else piso,
            )
    else:
        from app.search import hibrida

        def procurar(consulta):
            return hibrida.buscar(conexao, consulta, None)

    linhas = []
    for caso in casos:
        resultado = procurar(caso["consulta"])
        posicao = posicao_do_esperado(resultado.documentos, caso["esperado"])
        linhas.append(
            {
                "consulta": caso["consulta"],
                "esperado": caso["esperado"],
                "posicao": posicao,
                "total": len(resultado.documentos),
                "modo": resultado.modo,
            }
        )

    encontrados = [linha for linha in linhas if linha["posicao"]]
    # MRR: 1/posicao, media sobre todos os casos. Premia estar em primeiro
    # sem ignorar a diferenca entre estar em terceiro e nao estar de todo.
    mrr = sum(1 / linha["posicao"] for linha in encontrados) / len(linhas)

    resumo = {"casos": len(linhas), "mrr": round(mrr, 4)}
    for k in PROFUNDIDADES:
        acertos = sum(1 for linha in linhas if 0 < linha["posicao"] <= k)
        resumo[f"top{k}"] = acertos
    return {"resumo": resumo, "linhas": linhas}


def imprimir(relatorio: dict, detalhe: bool) -> None:
    resumo = relatorio["resumo"]
    total = resumo["casos"]
    print(f"{total} consultas avaliadas")
    for k in PROFUNDIDADES:
        acertos = resumo[f"top{k}"]
        print(f"  documento certo no top-{k:<2} {acertos:>3}/{total}"
              f"  ({acertos / total * 100:.0f}%)")
    print(f"  MRR                  {resumo['mrr']:.4f}")

    if not detalhe:
        return
    print()
    print(f"{'consulta':<28} {'pos':>4} {'res':>5}  esperado")
    for linha in relatorio["linhas"]:
        posicao = linha["posicao"] or "-"
        print(
            f"{linha['consulta'][:27]:<28} {str(posicao):>4} {linha['total']:>5}"
            f"  {linha['esperado'][:34]}"
        )


def comparar(atual: dict, antes: dict) -> None:
    """Mostra o que mudou por consulta, nao so a media.

    Uma media que sobe pode esconder consultas que pioraram; e nessas que
    esta a informacao util.
    """
    print()
    print("=== comparacao com a referencia ===")
    anterior = {linha["consulta"]: linha["posicao"] for linha in antes["linhas"]}

    melhores, piores = [], []
    for linha in atual["linhas"]:
        velha = anterior.get(linha["consulta"])
        if velha is None or velha == linha["posicao"]:
            continue
        # Nao aparecer conta como pior que qualquer posicao
        pontua = lambda p: p if p else 10**6  # noqa: E731
        (melhores if pontua(linha["posicao"]) < pontua(velha) else piores).append(
            (linha["consulta"], velha or "-", linha["posicao"] or "-")
        )

    for rotulo, itens in (("melhoraram", melhores), ("PIORARAM", piores)):
        if not itens:
            continue
        print(f"  {rotulo}:")
        for consulta, velha, nova in itens:
            print(f"    {consulta[:34]:<36} {velha} -> {nova}")
    if not melhores and not piores:
        print("  nenhuma consulta mudou de posicao")

    for chave in ("mrr", *[f"top{k}" for k in PROFUNDIDADES]):
        velho, novo = antes["resumo"][chave], atual["resumo"][chave]
        if velho != novo:
            seta = "+" if novo > velho else ""
            print(f"  {chave}: {velho} -> {novo} ({seta}{round(novo - velho, 4)})")


def main() -> None:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--detalhe", action="store_true")
    analisador.add_argument("--guardar", help="grava o resultado como referencia")
    analisador.add_argument("--comparar", help="compara com uma referencia gravada")
    analisador.add_argument(
        "--hibrido", action="store_true", help="junta a busca semantica"
    )
    analisador.add_argument(
        "--varrer-piso", action="store_true",
        help="mede varios pisos de semelhanca e mostra a tabela",
    )
    opcoes = analisador.parse_args()

    if not BANCO.exists():
        raise SystemExit(f"indice nao encontrado em {BANCO}")

    dados = json.loads(CONSULTAS.read_text(encoding="utf-8"))
    conexao = storage.abrir(BANCO)

    matriz = None
    if opcoes.hibrido or opcoes.varrer_piso:
        from app.search import semantica

        matriz = semantica.carregar_matriz(conexao)
        if matriz is None:
            raise SystemExit(
                "indice semantico vazio. Corra: python scripts/indexar_semantica.py"
            )
        print(f"indice semantico: {len(matriz)} fragmentos")
        print()

    if opcoes.varrer_piso:
        print(f"{'piso':>6} {'top1':>6} {'top3':>6} {'top10':>6} {'MRR':>8}")
        for piso in (0.0, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 1.1):
            r = avaliar(conexao, dados["casos"], matriz, piso)["resumo"]
            rotulo = "so lex" if piso > 1 else f"{piso:.2f}"
            print(f"{rotulo:>6} {r['top1']:>6} {r['top3']:>6}"
                  f" {r['top10']:>6} {r['mrr']:>8.4f}")
        conexao.close()
        return

    relatorio = avaliar(conexao, dados["casos"], matriz)
    conexao.close()

    imprimir(relatorio, opcoes.detalhe)

    if dados.get("lacunas"):
        print()
        print("lacunas de conteudo conhecidas (nenhuma ordenacao resolve):")
        for lacuna in dados["lacunas"]:
            print(f"  {lacuna['consulta'][:30]:<32} {lacuna['vezes']:>3}x"
                  f"  {lacuna['motivo']}")

    if opcoes.comparar:
        comparar(relatorio, json.loads(Path(opcoes.comparar).read_text("utf-8")))

    if opcoes.guardar:
        Path(opcoes.guardar).write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"\nreferencia gravada em {opcoes.guardar}")


if __name__ == "__main__":
    main()
