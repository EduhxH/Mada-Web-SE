import argparse
import sys
import time
from pathlib import Path

from app.crawler.local_source import MOTIVO_PRIVADO, Relatorio, carregar
from app.crawler import moodle
from app.crawler.web_source import rastrear
from app.analytics import uso
from app.indexing import atualizacao, storage
from app.indexing.inverted_index import construir_indice
from app.indexing.tokenizer import tokenizar
from app.interface import auth
from app.interface.web import iniciar
from app.search.query import MODO_OU, MODO_QUORUM, buscar_detalhado
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


def comando_buscar(consulta: str, disciplina: str | None = None) -> None:
    if not CAMINHO_BANCO.exists():
        print("Indice nao encontrado. Rode antes: python main.py indexar <caminho>")
        return
    conexao = storage.abrir(CAMINHO_BANCO)
    inicio = time.perf_counter()
    resultado = buscar_detalhado(conexao, consulta, disciplina)
    resultados = resultado.documentos
    duracao = time.perf_counter() - inicio
    conexao.close()

    escopo = f" em {disciplina}" if disciplina else ""
    corrigida = resultado.consulta_corrigida(consulta)
    if resultado.sugestoes and corrigida.lower() != consulta.lower():
        print(f'Sera que quis dizer: "{corrigida}"?')
    if not resultados:
        print(f'Nenhum resultado para "{consulta}"{escopo}.')
        return
    print(
        f'{len(resultados)} resultado(s) para "{consulta}"{escopo}'
        f" em {duracao * 1000:.1f} ms"
    )
    if resultado.correcao:
        print(f'A mostrar resultados para "{resultado.consulta_aplicada(consulta)}".')
    if resultado.modo == MODO_QUORUM:
        print(
            f"Nenhum documento tem os {resultado.termos_totais} termos;"
            f" a mostrar os que tem pelo menos {resultado.termos_exigidos}."
        )
    elif resultado.modo == MODO_OU:
        print("A mostrar documentos com algum dos termos.")
    print()
    termos = set(tokenizar(consulta))
    for posicao, (doc, pontuacao) in enumerate(resultados[:10], start=1):
        etiqueta = f"[{doc.disciplina}] " if doc.disciplina else ""
        print(f"{posicao:2d}. {etiqueta}{doc.titulo}   [{pontuacao:.4f}]")
        print(f"    {gerar_trecho(doc.texto, termos)}")
        print()
    if len(resultados) > 10:
        print(f"(mostrando os 10 primeiros de {len(resultados)})")


def comando_rastrear(url: str, pasta: str, paginas: int, profundidade: int,
                     intervalo: float) -> None:
    destino = Path("data") / "raw" / pasta
    print(f"A rastrear {url}")
    print(f"  limite: {paginas} paginas | profundidade: {profundidade}"
          f" | intervalo: {intervalo}s")
    inicio = time.perf_counter()
    relatorio = rastrear(
        url, destino,
        max_paginas=paginas,
        profundidade_maxima=profundidade,
        intervalo=intervalo,
    )
    duracao = time.perf_counter() - inicio
    print()
    html = relatorio.guardadas - relatorio.pdfs
    print(f"Guardadas {relatorio.guardadas} ({html} HTML + {relatorio.pdfs} PDF)"
          f" em {destino}")
    print(f"  {relatorio.pedidos} pedidos HTTP em {duracao:.1f}s"
          f" | profundidade atingida: {relatorio.profundidade_maxima_atingida}")
    if relatorio.ignoradas:
        print(f"  ignoradas: {len(relatorio.ignoradas)}")
        for motivo, quantos in sorted(
            relatorio.motivos().items(), key=lambda p: -p[1]
        ):
            print(f"    {motivo:<28} {quantos:>5}")
    print()
    print(f"Agora indexe: python main.py indexar data/raw")


def comando_atualizar(
    url: str, paginas: int, intervalo: float, sem_rastreio: bool
) -> None:
    inicio = time.perf_counter()

    if sem_rastreio:
        print("A saltar o rastreio do site (--sem-rastreio).")
    else:
        print(f"1/2  A rastrear {url} (max {paginas} paginas)...")
        relatorio_web = rastrear(
            url,
            Path("data") / "raw" / "Escola",
            max_paginas=paginas,
            intervalo=intervalo,
        )
        html = relatorio_web.guardadas - relatorio_web.pdfs
        print(
            f"     {relatorio_web.guardadas} guardadas"
            f" ({html} HTML + {relatorio_web.pdfs} PDF)"
            f" em {relatorio_web.pedidos} pedidos"
        )

    print("2/2  A reindexar o corpus completo...")
    alteracoes, relatorio, termos = atualizacao.reindexar()
    total = (
        alteracoes.mantidos + len(alteracoes.novos) + len(alteracoes.alterados)
    )
    if not total:
        print("     Nenhum documento encontrado.")
        imprimir_relatorio(relatorio)
        return

    duracao = time.perf_counter() - inicio
    print(f"     {total} documentos, {termos} termos unicos")
    print()
    print(f"Concluido em {duracao:.0f}s.  {alteracoes.resumo()}")

    for rotulo, itens in (
        ("Novos", alteracoes.novos),
        ("Alterados", alteracoes.alterados),
        ("Removidos", alteracoes.removidos),
    ):
        if not itens:
            continue
        print()
        print(f"{rotulo} ({len(itens)}):")
        for _, titulo in itens[:12]:
            print(f"  {titulo[:70]}")
        if len(itens) > 12:
            print(f"  ... e mais {len(itens) - 12}")

    if not alteracoes.houve_mudanca:
        print()
        print("O corpus esta igual ao da ultima atualizacao.")

    imprimir_relatorio(relatorio)


def comando_moodle(
    disciplinas: list[str] | None, intervalo: float, limite: int, listar: bool
) -> None:
    try:
        url_base, utilizador, _ = moodle.configuracao()
    except moodle.ErroMoodle as erro:
        print(erro)
        return

    print(f"A entrar em {url_base} como {utilizador}...")
    try:
        sessao = moodle.iniciar_sessao(*moodle.configuracao())
    except moodle.ErroMoodle as erro:
        print(f"  {erro}")
        return
    except Exception as erro:
        print(f"  Falhou: {erro}")
        return
    print("  Sessao iniciada.")

    todas = moodle.listar_disciplinas(sessao, url_base)
    if listar:
        print()
        print(f"{len(todas)} disciplina(s) inscritas:")
        for identificador, nome in todas:
            print(f"  {identificador:>6}  {nome}")
        return

    if not todas:
        print("  Nenhuma disciplina encontrada.")
        return

    raiz = Path("data") / "raw" / "psi9"
    inicio = time.perf_counter()

    def progresso(nome, quantos):
        print(f"  {nome[:46]:<48} {quantos:>3} recursos")

    print()
    relatorio = moodle.sincronizar(
        raiz,
        disciplinas_pedidas=disciplinas,
        intervalo=intervalo,
        limite_por_disciplina=limite,
        ao_progredir=progresso,
    )
    duracao = time.perf_counter() - inicio

    print()
    print(
        f"{relatorio.ficheiros} ficheiros"
        f" ({relatorio.bytes_totais / 1024 / 1024:.1f} MB)"
        f" em {relatorio.pedidos} pedidos, {duracao:.0f}s"
    )
    for nome, quantos in sorted(
        relatorio.disciplinas.items(), key=lambda p: -p[1]
    ):
        print(f"  {nome[:46]:<48} {quantos:>4}")

    if relatorio.ignorados:
        print()
        print(f"Ignorados: {len(relatorio.ignorados)}")
        motivos: dict[str, int] = {}
        for _, motivo in relatorio.ignorados:
            # manter o motivo completo: 'folder: sem ficheiros' e
            # 'folder: estado HTTP 404' sao problemas diferentes
            chave = motivo[:44]
            motivos[chave] = motivos.get(chave, 0) + 1
        for motivo, quantos in sorted(motivos.items(), key=lambda p: -p[1]):
            print(f"  {motivo:<46} {quantos:>4}")
        exemplos = [n for n, _ in relatorio.ignorados[:3]]
        if exemplos:
            print("  exemplos: " + ", ".join(e[:40] for e in exemplos))

    print()
    print("Agora indexe: python main.py atualizar --sem-rastreio")


def comando_disciplinas() -> None:
    if not CAMINHO_BANCO.exists():
        print("Indice nao encontrado. Rode antes: python main.py indexar <caminho>")
        return
    conexao = storage.abrir(CAMINHO_BANCO)
    for nome in storage.listar_disciplinas(conexao):
        quantos = len(storage.carregar_ids_por_disciplina(conexao, nome))
        print(f"  {nome:<40} {quantos:>5}")
    conexao.close()


def comando_participantes(
    criar: int, revogar: str | None, prefixo: str = "aluno"
) -> None:
    if revogar:
        if auth.revogar(revogar):
            print(f"Revogado: {revogar}")
        else:
            print(f"Nao encontrado: {revogar}")
        return

    if criar:
        novos = auth.criar_participantes(criar, prefixo)
        print("CODIGOS NOVOS - copie agora, nao voltam a ser mostrados:")
        print()
        for codigo, rotulo in novos.items():
            print(f"  {rotulo:<12} {codigo}")
        print()

    participantes = auth.carregar_participantes()
    if not participantes:
        print("Nenhum participante. Crie com: python main.py participantes --criar 8")
        return
    print(f"{len(participantes)} participante(s) ativo(s):")
    for rotulo in sorted(participantes.values()):
        print(f"  {rotulo}")
    print()
    print("Os codigos estao guardados como hash HMAC - nao sao recuperaveis.")
    print("Perdeu um codigo? Revogue e crie outro:")
    print("  python main.py participantes --revogar aluno-03 --criar 1")


def comando_estatisticas() -> None:
    conexao = uso.abrir()
    dados = uso.resumo(conexao)
    print("Resumo de utilizacao")
    print(f"  buscas .............. {dados['buscas']}")
    print(f"  participantes ....... {dados['participantes']}")
    print(f"  dias com uso ........ {dados['dias']}")
    print(f"  documentos abertos .. {dados['aberturas']}")
    print(f"  sem resultado ....... {dados['taxa_vazias']:.1f}%")
    print(f"  parciais (OU) ....... {dados['taxa_parciais']:.1f}%")
    print(f"  taxa de abertura .... {dados['taxa_abertura']:.1f}%")
    populares = uso.consultas_populares(conexao, 10)
    if populares:
        print()
        print("Consultas mais frequentes:")
        for consulta, vezes, vazias in populares:
            marca = f"  ({vazias} sem resultado)" if vazias else ""
            print(f"  {vezes:>3}x  {consulta}{marca}")
    falhadas = uso.consultas_sem_resultado(conexao, 10)
    if falhadas:
        print()
        print("Consultas que falharam:")
        for consulta, vezes in falhadas:
            print(f"  {vezes:>3}x  {consulta}")
    conexao.close()


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
    p_buscar.add_argument("--disciplina", help="restringe a uma disciplina")
    subcomandos.add_parser("disciplinas", help="lista as disciplinas indexadas")
    p_rastrear = subcomandos.add_parser(
        "rastrear", help="rastreia um site autorizado e guarda as paginas"
    )
    p_rastrear.add_argument("url")
    p_rastrear.add_argument("--pasta", default="Escola")
    p_rastrear.add_argument("--paginas", type=int, default=300)
    p_rastrear.add_argument("--profundidade", type=int, default=3)
    p_rastrear.add_argument("--intervalo", type=float, default=1.0)
    p_web = subcomandos.add_parser("web", help="inicia a interface web local")
    p_web.add_argument("--porta", type=int, default=8080)
    p_web.add_argument(
        "--host", default="127.0.0.1",
        help="use 0.0.0.0 para aceitar ligacoes de outros dispositivos",
    )
    p_part = subcomandos.add_parser(
        "participantes", help="lista ou cria codigos de acesso"
    )
    p_part.add_argument("--criar", type=int, default=0)
    p_part.add_argument("--revogar", help="rotulo a revogar, ex.: aluno-03")
    p_part.add_argument(
        "--admin", action="store_true",
        help="cria um codigo de administrador (ve as estatisticas completas)",
    )
    subcomandos.add_parser("estatisticas", help="resumo de utilizacao")
    p_atual = subcomandos.add_parser(
        "atualizar", help="rastreia o site, reindexa tudo e diz o que mudou"
    )
    p_atual.add_argument("--url", default="https://www.sefo.pt")
    p_atual.add_argument("--paginas", type=int, default=400)
    p_atual.add_argument("--intervalo", type=float, default=1.0)
    p_atual.add_argument(
        "--sem-rastreio", action="store_true",
        help="so reindexa o que ja esta em data/raw",
    )
    p_moodle = subcomandos.add_parser(
        "moodle", help="sincroniza materiais das suas disciplinas do Moodle"
    )
    p_moodle.add_argument(
        "--disciplina", action="append", dest="disciplinas",
        help="filtra por nome (pode repetir); por omissao, todas",
    )
    p_moodle.add_argument("--intervalo", type=float, default=1.0)
    p_moodle.add_argument(
        "--limite", type=int, default=0,
        help="max de recursos por disciplina (0 = sem limite)",
    )
    p_moodle.add_argument(
        "--listar", action="store_true",
        help="so mostra as disciplinas inscritas, nao descarrega nada",
    )

    argumentos = analisador.parse_args()
    if argumentos.comando == "indexar":
        comando_indexar(argumentos.caminho)
    elif argumentos.comando == "buscar":
        comando_buscar(argumentos.consulta, argumentos.disciplina)
    elif argumentos.comando == "rastrear":
        comando_rastrear(
            argumentos.url, argumentos.pasta, argumentos.paginas,
            argumentos.profundidade, argumentos.intervalo,
        )
    elif argumentos.comando == "disciplinas":
        comando_disciplinas()
    elif argumentos.comando == "web":
        iniciar(argumentos.porta, argumentos.host)
    elif argumentos.comando == "participantes":
        comando_participantes(
            argumentos.criar,
            argumentos.revogar,
            "admin" if argumentos.admin else "aluno",
        )
    elif argumentos.comando == "estatisticas":
        comando_estatisticas()
    elif argumentos.comando == "moodle":
        comando_moodle(
            argumentos.disciplinas,
            argumentos.intervalo,
            argumentos.limite,
            argumentos.listar,
        )
    elif argumentos.comando == "atualizar":
        comando_atualizar(
            argumentos.url,
            argumentos.paginas,
            argumentos.intervalo,
            argumentos.sem_rastreio,
        )
    else:
        modo_interativo()


if __name__ == "__main__":
    main()
