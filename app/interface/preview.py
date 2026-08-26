import html
from pathlib import Path

from app.indexing.tokenizer import tokenizar
from app.models.document import Documento
from app.search.snippet import gerar_trecho

RAIO_PREVIEW = 55


def resolver_origem(origem: str) -> tuple[Path, str | None, int | None, str]:
    resto = origem
    pagina = None
    rotulo = ""
    for marcador, nome in (("#pagina=", "pagina"), ("#slide=", "slide")):
        if marcador in resto:
            resto, numero = resto.split(marcador, 1)
            if numero.isdigit():
                pagina = int(numero)
                rotulo = nome
            break
    interno = None
    if "!" in resto:
        resto, interno = resto.split("!", 1)
    return Path(resto), interno, pagina, rotulo


def descrever(doc: Documento) -> dict[str, str]:
    if doc.origem.startswith(("http://", "https://")):
        endereco, _, pagina, rotulo = resolver_origem(doc.origem)
        e_pdf = str(endereco).lower().endswith(".pdf")
        dados = {
            "ficheiro": doc.origem.split("#")[0],
            "tipo": "PDF na web" if e_pdf else "pagina web",
            "disciplina": doc.disciplina,
            "palavras": f"{len(doc.texto.split())} palavras",
        }
        if pagina:
            dados["local"] = f"{rotulo} {pagina}"
        return dados
    caminho, interno, pagina, rotulo = resolver_origem(doc.origem)
    nome = Path(interno).name if interno else caminho.name
    extensao = Path(nome).suffix.lstrip(".").upper()
    dados = {
        "ficheiro": nome,
        "tipo": extensao or "ficheiro",
        "disciplina": doc.disciplina,
        "palavras": f"{len(doc.texto.split())} palavras",
    }
    if pagina:
        dados["local"] = f"{rotulo} {pagina}"
    if interno:
        dados["dentro_de"] = caminho.name
    return dados


def fragmento(doc: Documento, consulta: str) -> str:
    dados = descrever(doc)
    termos = set(tokenizar(consulta))

    etiquetas = [dados["tipo"]]
    if "local" in dados:
        etiquetas.append(dados["local"])
    etiquetas.append(dados["palavras"])
    if dados["disciplina"]:
        etiquetas.insert(0, dados["disciplina"])

    linhas = [
        '<p class="pv-etiquetas">'
        + " &middot; ".join(html.escape(e) for e in etiquetas)
        + "</p>",
        f'<p class="pv-ficheiro">{html.escape(dados["ficheiro"])}</p>',
    ]
    if "dentro_de" in dados:
        linhas.append(
            f'<p class="pv-zip">dentro de {html.escape(dados["dentro_de"])}</p>'
        )

    trecho = gerar_trecho(doc.texto, termos, raio=RAIO_PREVIEW)
    linhas.append(f'<p class="pv-texto">{_destacar(trecho, termos)}</p>')
    return "\n".join(linhas)


def _destacar(trecho: str, termos: set[str]) -> str:
    partes = []
    for palavra in trecho.split(" "):
        segura = html.escape(palavra)
        normalizada = tokenizar(palavra, remover_stop_words=False)
        if normalizada and normalizada[0] in termos:
            partes.append(f"<b>{segura}</b>")
        else:
            partes.append(segura)
    return " ".join(partes)
