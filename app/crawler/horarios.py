"""Vigia o horario da escola, que muda todas as semanas.

O horario nao vive numa disciplina: e um PDF unico com a escola toda - 42
paginas, uma ou duas por turma - publicado sempre no mesmo endereco, dentro
do Moodle. Substituido semanalmente, o URL nao muda; muda o ficheiro.

Isso torna a vigia barata: um pedido HEAD compara o ETag com o que ja
temos. So se mudou e que se descarregam as centenas de kilobytes.

Quando e que se verifica, tal como a escola funciona:

    quinta e sexta   a partir das 12h - e nessa tarde que costuma sair
    sabado e domingo a qualquer hora - se nao saiu nos dois dias uteis,
                     ainda pode sair no fim de semana
    resto da semana  nada, ja se sabe que nao sai

E assim que aparece um horario novo, a semana fica dada por resolvida e nao
se volta a incomodar o servidor ate a quinta seguinte. Uma semana comeca a
segunda-feira (semana ISO), portanto quinta, sexta, sabado e domingo caem
todos na mesma - o que e conveniente: "ja saiu esta semana" e uma pergunta
so.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CAMINHO_PDF = "/file.php/1/Documentos/horarios.pdf"
PASTA = Path("data") / "raw" / "horarios"
ESTADO = Path("data") / "horario-estado.json"
NOME_FICHEIRO = "horarios.pdf"
TITULO = "Horarios da escola"

# weekday(): segunda=0 ... domingo=6. Valor = hora a partir da qual verificar.
DIAS_DE_VIGIA = {3: 12, 4: 12, 5: 0, 6: 0}

TEMPO_LIMITE = 30


@dataclass
class Resultado:
    verificou: bool = False
    mudou: bool = False
    motivo: str = ""
    marca: str = ""
    bytes_guardados: int = 0


def ler_estado(caminho: Path = ESTADO) -> dict:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return dados if isinstance(dados, dict) else {}


def guardar_estado(estado: dict, caminho: Path = ESTADO) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def semana_de(momento: datetime) -> str:
    ano, semana, _ = momento.isocalendar()
    return f"{ano}-S{semana:02d}"


def deve_verificar(momento: datetime, estado: dict) -> tuple[bool, str]:
    """(verificar?, porque). O porque serve para o registo dizer alguma coisa."""
    if estado.get("semana_resolvida") == semana_de(momento):
        return False, "o horario desta semana ja foi apanhado"

    hora_minima = DIAS_DE_VIGIA.get(momento.weekday())
    if hora_minima is None:
        return False, "hoje o horario nao sai"
    if momento.hour < hora_minima:
        return False, f"ainda e cedo (sai a partir das {hora_minima}h)"
    return True, "dentro da janela de publicacao"


def marca_atual(sessao, url_base: str) -> str:
    """Identidade da versao publicada, sem descarregar o ficheiro.

    Prefere-se o ETag: muda sempre que o conteudo muda. O Last-Modified serve
    de alternativa quando o servidor nao da ETag.
    """
    resposta = sessao.head(
        f"{url_base}{CAMINHO_PDF}", timeout=TEMPO_LIMITE, allow_redirects=True
    )
    if resposta.status_code != 200:
        return ""
    etiqueta = resposta.headers.get("ETag") or resposta.headers.get("Last-Modified")
    return (etiqueta or "").strip()


def descarregar(sessao, url_base: str, pasta: Path = PASTA) -> int:
    """Guarda o PDF e o manifesto que diz de onde veio. Devolve os bytes."""
    endereco = f"{url_base}{CAMINHO_PDF}"
    resposta = sessao.get(endereco, timeout=TEMPO_LIMITE)
    if resposta.status_code != 200 or not resposta.content.startswith(b"%PDF"):
        return 0

    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / NOME_FICHEIRO).write_bytes(resposta.content)

    from app.crawler.moodle import data_da_resposta

    registo = {"url": endereco, "titulo": TITULO}
    data = data_da_resposta(resposta)
    if data:
        registo["data"] = data
    (pasta / "_origens.json").write_text(
        json.dumps({NOME_FICHEIRO: registo}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return len(resposta.content)


def verificar(
    sessao, url_base: str, momento: datetime | None = None,
    pasta: Path = PASTA, caminho_estado: Path = ESTADO,
    forcar: bool = False,
) -> Resultado:
    agora = momento or datetime.now()
    estado = ler_estado(caminho_estado)

    if not forcar:
        vale_a_pena, motivo = deve_verificar(agora, estado)
        if not vale_a_pena:
            return Resultado(verificou=False, motivo=motivo)

    marca = marca_atual(sessao, url_base)
    if not marca:
        return Resultado(verificou=True, motivo="o servidor nao respondeu ao HEAD")

    estado["ultima_verificacao"] = agora.isoformat(timespec="seconds")
    if marca == estado.get("marca"):
        guardar_estado(estado, caminho_estado)
        return Resultado(
            verificou=True, mudou=False, marca=marca,
            motivo="o horario publicado ainda e o mesmo",
        )

    guardados = descarregar(sessao, url_base, pasta)
    if not guardados:
        guardar_estado(estado, caminho_estado)
        return Resultado(
            verificou=True, marca=marca,
            motivo="mudou, mas o ficheiro nao veio inteiro",
        )

    estado["marca"] = marca
    estado["semana_resolvida"] = semana_de(agora)
    estado["ultima_mudanca"] = agora.isoformat(timespec="seconds")
    guardar_estado(estado, caminho_estado)
    return Resultado(
        verificou=True, mudou=True, marca=marca, bytes_guardados=guardados,
        motivo="horario novo",
    )
