import argparse
import sys
import time
from pathlib import Path

from app.crawler.local_source import MOTIVO_PRIVADO, Relatorio, carregar
from app.indexing import storage
from app.indexing.inverted_index import construir_indice
from app.indexing.tokenizer import tokenizar
from app.interface.web import iniciar
from app.search.query import buscar
from app.search.snippet import gerar_trecho

CAMINHO_BANCO = Path("data") / "indice.sqlite3"


def imprimir_relatorio(relatorio: Relatorio) -> None:
    print()
    print("Por disciplina:")
    for disciplina, quantos in relatorio.por_disciplina.most_common():
        print(f"  {disciplina:<40} {quantos:>5}")

    print()
    print("Por formato:")
    for formato, quantos in relatorio.por_formato.most_common():
        print(f"  {formato:<40} {quantos:>5}")

    if not relatorio.ignorados:
        return

    print()
    print(f"Ignorados: {len(relatorio.ignorados)}")
    for motivo, quantos in relatorio.motivos().most_common():
        print(f"  {motivo:<40} {quantos:>5}")

    privados = relatorio.por_motivo(MOTIVO_PRIVADO)
    if privados:
        print()
        print("Excluidos por possivel dado pessoal:")
        for nome in privados:
            print(f"  {Path(nome).name}")


def comando_indexar(caminho: str) -> None:
    inicio = time.perf_counter()
    documentos, relatorio = carregar(caminho)
    if not documentos:
        print("Nenhum documento com texto encontrado em:", caminho)
        imprimir_relatorio(relatorio)
        return
    indice, tamanhos = construir_indice(documentos)
    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = storage.abrir(CAMINHO_BANCO)
    storage.salvar_indice(conexao, documentos, indice, tamanhos)
    conexao.close()
    duracao = time.perf_counter() - inicio
    print(f"Indexados {len(documentos)} documentos, {len(indice)} termos unicos,")
    print(f"em {duracao:.2f}s. Indice salvo em {CAMINHO_BANCO}")
    imprimir_relatorio(relatorio)


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
        etiqueta = f"[{doc.disciplina}] " if doc.disciplina else ""
        print(f"{posicao:2d}. {etiqueta}{doc.titulo}   [{pontuacao:.4f}]")
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
    p_web = subcomandos.add_parser("web", help="inicia a interface web local")
    p_web.add_argument("--porta", type=int, default=8080)

    argumentos = analisador.parse_args()
    if argumentos.comando == "indexar":
        comando_indexar(argumentos.caminho)
    elif argumentos.comando == "buscar":
        comando_buscar(argumentos.consulta)
    elif argumentos.comando == "web":
        iniciar(argumentos.porta)
    else:
        modo_interativo()


if __name__ == "__main__":
    main()
