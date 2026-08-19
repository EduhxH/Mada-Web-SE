import argparse
import sys
import time
from pathlib import Path

from app.crawler.local_source import carregar
from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.indexing.tokenizer import tokenizar
from app.search.query import buscar

CAMINHO_BANCO = Path("data") / "indice.sqlite3"


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


def comando_indexar(caminho: str) -> None:
    inicio = time.perf_counter()
    documentos = carregar(caminho)
    if not documentos:
        print("Nenhum documento com texto encontrado em:", caminho)
        return
    indice, tamanhos = construir_indice(documentos)
    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = storage.abrir(CAMINHO_BANCO)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    conexao.close()
    duracao = time.perf_counter() - inicio
    print(f"Indexados {len(documentos)} documentos, {len(indice)} termos unicos,")
    print(f"em {duracao:.2f}s. Indice salvo em {CAMINHO_BANCO}")


def comando_buscar(consulta: str) -> None:
    if not CAMINHO_BANCO.exists():
        print("Indice nao encontrado. Rode antes: python main.py indexar <caminho>")
        return
    conexao = storage.abrir(CAMINHO_BANCO)
    inicio = time.perf_counter()
    resultados = buscar(conexao, consulta)
    duracao = time.perf_counter() - inicio
    conexao.close()

    if not resultados:
        print(f'Nenhum resultado para "{consulta}".')
        return
    print(f'{len(resultados)} resultado(s) para "{consulta}" em {duracao * 1000:.1f} ms')
    print()
    termos = set(tokenizar(consulta))
    for posicao, (doc, pontuacao) in enumerate(resultados[:10], start=1):
        print(f"{posicao:2d}. {doc.titulo}   [{pontuacao:.4f}]")
        print(f"    {gerar_trecho(doc.texto, termos)}")
        print()
    if len(resultados) > 10:
        print(f"(mostrando os 10 primeiros de {len(resultados)})")


def modo_interativo() -> None:
    print("Motor de busca - modo interativo. Vazio ou 'sair' encerra.")
    while True:
        try:
            consulta = input("busca> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not consulta or consulta.lower() == "sair":
            break
        comando_buscar(consulta)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    analisador = argparse.ArgumentParser(description="Motor de busca educacional")
    subcomandos = analisador.add_subparsers(dest="comando")
    p_indexar = subcomandos.add_parser("indexar", help="indexa um arquivo ou pasta")
    p_indexar.add_argument("caminho")
    p_buscar = subcomandos.add_parser("buscar", help="busca no indice existente")
    p_buscar.add_argument("consulta")

    argumentos = analisador.parse_args()
    if argumentos.comando == "indexar":
        comando_indexar(argumentos.caminho)
    elif argumentos.comando == "buscar":
        comando_buscar(argumentos.consulta)
    else:
        modo_interativo()


if __name__ == "__main__":
    main()
