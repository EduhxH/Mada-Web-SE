"""Os posts da newsletter: escritos no painel, lidos em /novidades.

Fica em `models` pela mesma razao que `novidades`: e lido dos dois lados. O
painel escreve, a pagina dos alunos le. Se vivesse num deles, o outro tinha de
importar de onde nao deve.

Um ficheiro JSON e suficiente e continua a ser a escolha certa - sao alguns
posts por periodo, escritos um de cada vez por uma pessoa. O que isto NAO tem,
por nao fazer falta, e escrita concorrente: ha um administrador, e se um dia
houver dois a escrever ao mesmo tempo, o ultimo a guardar ganha. Para nao perder
o ficheiro inteiro numa falha a meio da escrita, grava-se para um ficheiro ao
lado e troca-se no fim - o `replace` e atomico no mesmo volume.

O ficheiro e `{"proximo": N, "posts": [...]}` e nao uma lista solta, porque o
contador de ids tem de sobreviver ao apagar. Deduzi-lo do maior id presente
fazia o post mais recente devolver o seu numero assim que fosse apagado. A forma
antiga - uma lista - continua a ser lida, para nao partir o que ja esta em disco.

**A separacao entre rascunho e publicado importa.** Um post nasce rascunho: e
visivel so no painel. O aluno so ve o que foi publicado de proposito, o que
permite escrever a meio de uma aula sem ninguem ler por cima do ombro.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

CAMINHO_PADRAO = Path("data") / "newsletter.json"

# Um periodo escolar de posts. Acima disto e historico que ninguem le, e a
# pagina passava a carregar tudo para mostrar os primeiros cinco.
MAXIMO_POSTS = 200

LIMITE_TITULO = 140
LIMITE_CORPO = 20000


@dataclass
class Post:
    id: int
    titulo: str
    corpo: str
    autor: str
    criado: str
    atualizado: str
    publicado: bool = False

    @property
    def data_curta(self) -> str:
        return (self.criado or "")[:10]

    def como_json(self) -> dict:
        return asdict(self)


def _ler_ficheiro(caminho: Path) -> dict:
    """`{"proximo": N, "posts": [...]}`.

    Aceita tambem a forma antiga - uma lista de posts, sem contador - porque foi
    assim que o ficheiro nasceu e nao ha razao para partir o que ja esta escrito
    no disco. Nesse caso o contador e deduzido do maior id presente, o que
    devolve o comportamento de antes e nada pior.
    """
    if not caminho.exists():
        return {"proximo": 1, "posts": []}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"proximo": 1, "posts": []}

    if isinstance(dados, list):
        posts, proximo = dados, 0
    elif isinstance(dados, dict):
        posts = dados.get("posts")
        proximo = dados.get("proximo")
        if not isinstance(posts, list) or not isinstance(proximo, int):
            return {"proximo": 1, "posts": []}
    else:
        return {"proximo": 1, "posts": []}

    maior = max(
        (int(b["id"]) for b in posts if str(b.get("id", "")).isdigit()), default=0
    )
    return {"proximo": max(proximo, maior + 1, 1), "posts": posts}


def _ler(caminho: Path) -> list[dict]:
    return _ler_ficheiro(caminho)["posts"]


def _escrever(caminho: Path, posts: list[dict], proximo: int) -> None:
    """Grava ao lado e troca. Uma falha a meio nao deixa o ficheiro meio escrito."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    provisorio = caminho.with_name(caminho.name + ".novo")
    provisorio.write_text(
        json.dumps(
            {"proximo": proximo, "posts": posts[-MAXIMO_POSTS:]},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    provisorio.replace(caminho)


def _para_post(bruto: dict) -> Post | None:
    try:
        return Post(
            id=int(bruto["id"]),
            titulo=str(bruto.get("titulo", "")),
            corpo=str(bruto.get("corpo", "")),
            autor=str(bruto.get("autor", "")),
            criado=str(bruto.get("criado", "")),
            atualizado=str(bruto.get("atualizado", "")),
            publicado=bool(bruto.get("publicado", False)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def listar(
    so_publicados: bool = False, caminho: Path | None = None
) -> list[Post]:
    """Do mais recente para o mais antigo, pela data de criacao."""
    caminho = caminho or CAMINHO_PADRAO
    posts = [p for p in (_para_post(b) for b in _ler(caminho)) if p is not None]
    if so_publicados:
        posts = [p for p in posts if p.publicado]
    return sorted(posts, key=lambda p: (p.criado, p.id), reverse=True)


def obter(identificador: int, caminho: Path | None = None) -> Post | None:
    for post in listar(caminho=caminho):
        if post.id == identificador:
            return post
    return None


def guardar(
    titulo: str,
    corpo: str,
    autor: str,
    identificador: int | None = None,
    publicado: bool | None = None,
    caminho: Path | None = None,
    agora: str | None = None,
) -> Post:
    """Cria ou actualiza. Devolve o post como ficou guardado."""
    caminho = caminho or CAMINHO_PADRAO
    ficheiro = _ler_ficheiro(caminho)
    brutos, proximo = ficheiro["posts"], ficheiro["proximo"]
    momento = agora or datetime.now().isoformat(timespec="seconds")
    titulo = (titulo or "").strip()[:LIMITE_TITULO]
    corpo = (corpo or "")[:LIMITE_CORPO]

    if identificador is not None:
        for bruto in brutos:
            if str(bruto.get("id")) != str(identificador):
                continue
            bruto["titulo"] = titulo
            bruto["corpo"] = corpo
            bruto["atualizado"] = momento
            if publicado is not None:
                bruto["publicado"] = bool(publicado)
            _escrever(caminho, brutos, proximo)
            return _para_post(bruto)

    novo = {
        "id": proximo,
        "titulo": titulo,
        "corpo": corpo,
        "autor": autor,
        "criado": momento,
        "atualizado": momento,
        "publicado": bool(publicado),
    }
    brutos.append(novo)
    _escrever(caminho, brutos, proximo + 1)
    return _para_post(novo)


def marcar_publicado(
    identificador: int, publicado: bool, caminho: Path | None = None
) -> Post | None:
    caminho = caminho or CAMINHO_PADRAO
    ficheiro = _ler_ficheiro(caminho)
    for bruto in ficheiro["posts"]:
        if str(bruto.get("id")) != str(identificador):
            continue
        bruto["publicado"] = bool(publicado)
        bruto["atualizado"] = datetime.now().isoformat(timespec="seconds")
        _escrever(caminho, ficheiro["posts"], ficheiro["proximo"])
        return _para_post(bruto)
    return None


def apagar(identificador: int, caminho: Path | None = None) -> bool:
    caminho = caminho or CAMINHO_PADRAO
    ficheiro = _ler_ficheiro(caminho)
    brutos = ficheiro["posts"]
    restantes = [b for b in brutos if str(b.get("id")) != str(identificador)]
    if len(restantes) == len(brutos):
        return False
    # O contador nao desce. Apagar o post 2 nao pode fazer o proximo ser 2 outra
    # vez: um id reciclado faz uma ligacao antiga apontar para outro texto, e e
    # o tipo de coisa que ninguem repara ate reparar.
    _escrever(caminho, restantes, ficheiro["proximo"])
    return True


def contar(caminho: Path | None = None) -> tuple[int, int]:
    """(publicados, rascunhos)."""
    posts = listar(caminho=caminho)
    publicados = sum(1 for p in posts if p.publicado)
    return publicados, len(posts) - publicados


def mais_recente_publicado(caminho: Path | None = None) -> Post | None:
    publicados = listar(so_publicados=True, caminho=caminho)
    return publicados[0] if publicados else None
