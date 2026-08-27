import html
from urllib.parse import urlencode

from app.analytics import uso
from app.indexing import storage
from app.search import temas as temas_mod

LIMITE_TEMAS = temas_mod.LIMITE_TEMAS
LIMITE_DOCUMENTOS = 8

_cache_temas: dict[tuple[str, int], list[str]] = {}


def temas(conexao_indice, disciplina: str, limite: int = LIMITE_TEMAS) -> list[str]:
    chave = (disciplina, storage.contar_documentos(conexao_indice))
    if chave not in _cache_temas:
        _cache_temas[chave] = temas_mod.extrair(conexao_indice, disciplina)
    return _cache_temas[chave][:limite]


def limpar_cache() -> None:
    _cache_temas.clear()


def _ligacao(consulta: str, disciplina: str) -> str:
    return "/?" + urlencode({"q": consulta, "d": disciplina})


def _seccao(titulo: str, corpo: str) -> str:
    if not corpo:
        return ""
    return f'<h2 class="dsc">{html.escape(titulo)}</h2>{corpo}'


def pagina(conexao_indice, conexao_uso, disciplina: str) -> str:
    quantos = storage.contar_por_disciplina(conexao_indice, disciplina)
    if not quantos:
        return f'<p class="vazio">Nada indexado em {html.escape(disciplina)}.</p>'

    blocos = [
        f'<p class="meta">{quantos} documento(s) em '
        f"<b>{html.escape(disciplina)}</b></p>"
    ]

    fichas = "".join(
        f'<a class="tema" href="{html.escape(_ligacao(termo, disciplina))}">'
        f"{html.escape(termo)}</a>"
        for termo in temas(conexao_indice, disciplina)
    )
    blocos.append(_seccao("Temas frequentes", f'<div class="temas">{fichas}</div>'))

    procuradas = uso.consultas_da_disciplina(conexao_uso, disciplina)
    if procuradas:
        linhas = "".join(
            f'<li><a href="{html.escape(_ligacao(consulta, disciplina))}">'
            f"{html.escape(consulta)}</a> <span class=\"vezes\">{vezes}x</span></li>"
            for consulta, vezes in procuradas
        )
        blocos.append(_seccao("A turma procurou por", f"<ul class='dsc'>{linhas}</ul>"))

    abertos = uso.documentos_mais_abertos(conexao_uso)
    if abertos:
        detalhes = storage.disciplinas_dos_documentos(
            conexao_indice, [doc_id for doc_id, _ in abertos]
        )
        linhas = []
        for doc_id, vezes in abertos:
            info = detalhes.get(doc_id)
            if not info or info[0] != disciplina:
                continue
            linhas.append(
                f'<li><a href="/documento?id={doc_id}" target="_blank" rel="noopener">'
                f"{html.escape(info[1])}</a> "
                f'<span class="vezes">{vezes}x</span></li>'
            )
            if len(linhas) >= LIMITE_DOCUMENTOS:
                break
        if linhas:
            blocos.append(
                _seccao("Mais abertos nesta disciplina", f"<ul class='dsc'>{''.join(linhas)}</ul>")
            )

    documentos = storage.documentos_da_disciplina(
        conexao_indice, disciplina, LIMITE_DOCUMENTOS
    )
    if documentos:
        linhas = "".join(
            f'<li><a href="/documento?id={doc_id}" target="_blank" rel="noopener">'
            f"{html.escape(titulo)}</a></li>"
            for doc_id, titulo in documentos
        )
        blocos.append(_seccao("Documentos com mais conteudo", f"<ul class='dsc'>{linhas}</ul>"))

    return "\n".join(bloco for bloco in blocos if bloco)
