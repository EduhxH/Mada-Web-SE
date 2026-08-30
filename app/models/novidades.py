"""Registo do material que apareceu no Moodle, para a interface o mostrar.

Fica em models porque e lido dos dois lados: o conector escreve depois de
sincronizar, a interface le para dizer aos alunos o que ha de novo. Se
vivesse num dos dois, o outro tinha de importar de onde nao deve.

Um ficheiro JSON chega: sao dezenas de entradas por periodo, escritas uma
vez por dia. Uma base de dados aqui era peso sem retorno.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

CAMINHO_PADRAO = Path("data") / "novidades.json"
# Um periodo escolar chega para o historico; o resto e ruido.
MAXIMO_ENTRADAS = 300
DIAS_RECENTES = 7


@dataclass(frozen=True)
class Novidade:
    data: str
    disciplina: str
    titulo: str
    url: str

    @property
    def quando(self) -> date:
        return datetime.strptime(self.data, "%Y-%m-%d").date()


def _ler(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return dados if isinstance(dados, list) else []


def registar(
    entradas: list[tuple[str, str, str]],
    caminho: Path | None = None,
    quando: date | None = None,
) -> int:
    """Acrescenta (disciplina, titulo, url) ao registo. Devolve quantas entraram.

    Repetidos sao ignorados pelo url: uma verificacao que corra duas vezes no
    mesmo dia nao duplica a lista.
    """
    if not entradas:
        return 0
    caminho = caminho or CAMINHO_PADRAO
    existentes = _ler(caminho)
    jaLa = {e.get("url") for e in existentes}
    dia = (quando or date.today()).isoformat()

    novas = [
        {"data": dia, "disciplina": d, "titulo": t, "url": u}
        for d, t, u in entradas
        if u not in jaLa
    ]
    if not novas:
        return 0

    caminho.parent.mkdir(parents=True, exist_ok=True)
    juntas = (existentes + novas)[-MAXIMO_ENTRADAS:]
    caminho.write_text(
        json.dumps(juntas, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return len(novas)


def recentes(
    dias: int = DIAS_RECENTES,
    caminho: Path | None = None,
    hoje: date | None = None,
) -> list[Novidade]:
    """As novidades dos ultimos dias, da mais recente para a mais antiga."""
    caminho = caminho or CAMINHO_PADRAO
    limite = (hoje or date.today()) - timedelta(days=dias)
    encontradas = []
    for bruto in _ler(caminho):
        try:
            item = Novidade(
                bruto["data"], bruto["disciplina"], bruto["titulo"], bruto["url"]
            )
        except (KeyError, TypeError):
            continue
        try:
            if item.quando > limite:
                encontradas.append(item)
        except ValueError:
            continue
    return sorted(encontradas, key=lambda n: n.data, reverse=True)


def contar_recentes(
    dias: int = DIAS_RECENTES,
    caminho: Path | None = None,
    hoje: date | None = None,
) -> int:
    return len(recentes(dias, caminho, hoje))
