import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.indexing import storage
from app.models.document import Documento
from app.search.naive import buscar_ingenua
from app.search.query import buscar

CAMINHO_BANCO = Path("data") / "indice.sqlite3"


def principal() -> None:
    consulta = sys.argv[1] if len(sys.argv) > 1 else "arquitetura limpa"
    if not CAMINHO_BANCO.exists():
        print("Indice nao encontrado. Rode antes: python main.py indexar <caminho>")
        return
    conexao = storage.abrir(CAMINHO_BANCO)
    linhas = conexao.execute(
        "SELECT id, titulo, texto, origem FROM documents"
    ).fetchall()
    documentos = [Documento(*linha) for linha in linhas]

    inicio = time.perf_counter()
    resultado_ingenuo = buscar_ingenua(consulta, documentos)
    tempo_ingenuo = time.perf_counter() - inicio

    inicio = time.perf_counter()
    resultado_indexado = buscar(conexao, consulta)
    tempo_indexado = time.perf_counter() - inicio
    conexao.close()

    iguais = {d.id for d in resultado_ingenuo} == {
        d.id for d, _ in resultado_indexado
    }
    print(f'Consulta: "{consulta}" sobre {len(documentos)} documentos')
    print(f"Busca ingenua:  {tempo_ingenuo * 1000:8.1f} ms ({len(resultado_ingenuo)} resultados)")
    print(f"Busca indexada: {tempo_indexado * 1000:8.1f} ms ({len(resultado_indexado)} resultados)")
    print("Mesmos documentos encontrados:", "sim" if iguais else "NAO - BUG!")
    if tempo_indexado > 0:
        print(f"Aceleracao: {tempo_ingenuo / tempo_indexado:.0f}x")


if __name__ == "__main__":
    principal()
