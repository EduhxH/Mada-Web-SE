"""Constroi o indice semantico a partir do indice lexical ja existente.

Corre uma vez (ou depois de uma atualizacao do corpus). Neste CPU sao cerca
de 40 minutos para o corpus todo, por isso guarda o progresso a cada lote:
uma interrupcao nao obriga a comecar do zero.

Uso:
    python scripts/indexar_semantica.py
    python scripts/indexar_semantica.py --recomecar
    python scripts/indexar_semantica.py --limite 200
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.indexing import storage  # noqa: E402
from app.search import semantica  # noqa: E402

BANCO = RAIZ / "data" / "indice.sqlite3"
LOTE = 64


def documentos_por_fazer(conexao, limite: int) -> list[tuple[int, str, str]]:
    consulta = """
        SELECT d.id, d.titulo, d.texto FROM documents d
        WHERE NOT EXISTS (SELECT 1 FROM fragmentos f WHERE f.doc_id = d.id)
        ORDER BY d.id
    """
    if limite:
        consulta += f" LIMIT {int(limite)}"
    return conexao.execute(consulta).fetchall()


def main() -> None:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--recomecar", action="store_true")
    analisador.add_argument("--limite", type=int, default=0)
    opcoes = analisador.parse_args()

    if not BANCO.exists():
        raise SystemExit(f"indice lexical nao encontrado em {BANCO}")

    conexao = storage.abrir(BANCO)
    semantica.criar_esquema(conexao)
    if opcoes.recomecar:
        conexao.execute("DELETE FROM fragmentos")
        conexao.commit()
        print("indice semantico apagado")

    # Reindexar o corpus reescreve a tabela de documentos. Como os ids sao
    # estaveis, quase todos os fragmentos continuam validos; os que sobram
    # sao de documentos que desapareceram e teriam de ser limpos a mao.
    orfaos = conexao.execute(
        "DELETE FROM fragmentos WHERE doc_id NOT IN (SELECT id FROM documents)"
    ).rowcount
    if orfaos > 0:
        conexao.commit()
        print(f"{orfaos} fragmentos de documentos que ja nao existem, removidos")

    pendentes = documentos_por_fazer(conexao, opcoes.limite)
    if not pendentes:
        total = conexao.execute("SELECT COUNT(*) FROM fragmentos").fetchone()[0]
        print(f"nada por fazer: {total} fragmentos ja indexados")
        return

    print(f"{len(pendentes)} documentos por indexar")
    semantica.carregar_modelo()

    inicio = time.perf_counter()
    feitos = fragmentos_totais = 0
    pendura: list[tuple[int, list[str]]] = []
    acumulado: list[str] = []

    def descarregar() -> None:
        nonlocal fragmentos_totais, acumulado, pendura
        if not acumulado:
            return
        vetores = semantica.embeber(acumulado)
        posicao = 0
        for doc_id, fragmentos in pendura:
            fatia = vetores[posicao : posicao + len(fragmentos)]
            semantica.guardar(conexao, doc_id, fragmentos, fatia)
            posicao += len(fragmentos)
            fragmentos_totais += len(fragmentos)
        conexao.commit()
        pendura, acumulado = [], []

    for doc_id, titulo, texto in pendentes:
        fragmentos = semantica.fragmentar(texto)
        if not fragmentos:
            feitos += 1
            continue
        pendura.append((doc_id, fragmentos))
        acumulado.extend(
            semantica.preparar(fragmento, titulo) for fragmento in fragmentos
        )
        feitos += 1

        if len(acumulado) >= LOTE:
            descarregar()
            decorrido = time.perf_counter() - inicio
            ritmo = fragmentos_totais / decorrido if decorrido else 0
            restantes = len(pendentes) - feitos
            print(
                f"  {feitos}/{len(pendentes)} documentos"
                f" | {fragmentos_totais} fragmentos"
                f" | {ritmo:.1f}/s"
                f" | faltam ~{restantes * (fragmentos_totais / max(feitos, 1)) / max(ritmo, 0.1) / 60:.0f} min",
                flush=True,
            )

    descarregar()
    decorrido = time.perf_counter() - inicio
    print(
        f"concluido: {fragmentos_totais} fragmentos de {feitos} documentos"
        f" em {decorrido / 60:.1f} min"
    )


if __name__ == "__main__":
    main()
