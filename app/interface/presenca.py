"""Quem esta online, de que aparelho, e a fazer o que.

Vive a parte do registo de uso porque responde a uma pergunta diferente. O
registo de uso e historico - serve para afinar o motor contra o que a turma
procurou durante um periodo. A presenca e o agora, e so o agora: uma linha por
pessoa, reescrita, sem historico nenhum.

**O que isto deliberadamente nao guarda.** Nem o endereco IP nem a cadeia
User-Agent. O painel precisa de desenhar um icone de telemovel ou de
computador, e para isso basta a palavra - guardar a cadeia completa era guardar
uma impressao digital do aparelho para pintar um icone de dezesseis pixeis. O
IP nunca foi guardado em sitio nenhum do projeto e nao vai comecar aqui.

**Porque e que a escrita e estrangulada.** Marcar presenca e um UPSERT numa
tabela de oito linhas: menos de um milissegundo. Mas o indice esta num disco
mecanico, e cada aluno faz vinte pedidos por minuto a pesquisar - com
sugestoes e pre-visualizacoes pelo meio. Escrever a cada pedido seria escrever
cem vezes mais do que a informacao muda: ninguem distingue "visto ha 4
segundos" de "visto ha 30". Guarda-se em memoria a ultima escrita de cada
pessoa e so se vai ao disco passados `SEGUNDOS_ENTRE_ESCRITAS`.
"""

import threading
import time
from datetime import datetime, timezone

from app.analytics import uso

# Intervalo minimo entre duas escritas da mesma pessoa. Trinta segundos: o
# limite de "online" e de cinco minutos, portanto trinta segundos de atraso na
# ultima visita nao muda nenhuma decisao do painel.
SEGUNDOS_ENTRE_ESCRITAS = 30

TELEMOVEL = "telemovel"
TABLET = "tablet"
COMPUTADOR = "computador"
DESCONHECIDO = "desconhecido"

# Palavras que decidem o aparelho. A ordem importa: um iPad diz "Mobile" na
# mesma cadeia em que diz "iPad", e um tablet Android diz "Android" sem dizer
# "Mobi" - e por isso que o tablet e testado primeiro e o Android depois.
_TABLET = ("ipad", "tablet", "playbook", "silk", "kindle")
_TELEMOVEL = (
    "iphone", "ipod", "windows phone", "blackberry", "opera mini",
    "mobi", "phone",
)

_ultima_escrita: dict[str, float] = {}
_tranca = threading.Lock()


def dispositivo_de(agente: str | None) -> str:
    """`telemovel`, `tablet`, `computador` ou `desconhecido`.

    Uma heuristica sobre o User-Agent, que e o que existe - nao ha forma
    honesta de saber o aparelho de outra maneira. Erra em casos de fronteira
    (um telemovel em "modo computador" diz que e um computador) e isso e
    aceitavel: o icone e informacao de apoio, nao decide nada.
    """
    if not agente:
        return DESCONHECIDO
    baixo = agente.lower()
    if any(marca in baixo for marca in _TABLET):
        return TABLET
    # "android" sozinho e tablet; com "mobi" e telemovel. A regra e do proprio
    # Google e e a unica forma de separar os dois no Android.
    if "android" in baixo:
        return TELEMOVEL if "mobi" in baixo else TABLET
    if any(marca in baixo for marca in _TELEMOVEL):
        return TELEMOVEL
    return COMPUTADOR


def pagina_de(caminho: str) -> str:
    """O caminho reduzido a uma palavra, para mostrar onde a pessoa esta.

    Reduzir e o ponto: guardar `/documento?id=412&q=criterios+de+avaliacao`
    punha a consulta dentro da tabela de presenca, onde nao tem nada que fazer -
    ja esta nos eventos, com prazo de validade. Aqui fica "documento".
    """
    limpo = (caminho or "/").split("?")[0].strip("/")
    if not limpo:
        return "busca"
    return limpo.split("/")[0][:24]


def marcar(participante: str, agente: str | None, caminho: str) -> None:
    """Anota que esta pessoa esteve aqui agora. Silencioso se falhar.

    Nunca levanta: isto corre no caminho de cada pedido, e um problema a
    escrever "quem esta online" nao pode ser motivo para uma busca falhar.
    """
    agora = time.monotonic()
    with _tranca:
        ultima = _ultima_escrita.get(participante, 0.0)
        if agora - ultima < SEGUNDOS_ENTRE_ESCRITAS:
            return
        _ultima_escrita[participante] = agora
    try:
        with uso.partilhada() as registo:
            uso.marcar_presenca(
                registo, participante, dispositivo_de(agente), pagina_de(caminho)
            )
    except Exception:
        # Deixar o carimbo em memoria mesmo assim: se a base de dados esta com
        # problemas, tentar outra vez em cada pedido so piora.
        pass


def esquecer_cache() -> None:
    """Para os testes, e para depois de apagar a presenca a mao."""
    with _tranca:
        _ultima_escrita.clear()


def segundos_desde(visto: str | None, agora: datetime | None = None) -> int | None:
    """Quantos segundos desde `visto` (ISO em UTC). None se nao se sabe."""
    if not visto:
        return None
    try:
        marca = datetime.fromisoformat(visto)
    except ValueError:
        return None
    if marca.tzinfo is None:
        marca = marca.replace(tzinfo=timezone.utc)
    agora = agora or datetime.now(timezone.utc)
    return max(0, int((agora - marca).total_seconds()))


def esta_online(visto: str | None, agora: datetime | None = None) -> bool:
    idade = segundos_desde(visto, agora)
    return idade is not None and idade < uso.SEGUNDOS_ONLINE


def ha_quanto_tempo(segundos: int | None) -> str:
    """"agora mesmo", "ha 4 min", "ha 3 h", "ha 2 dias", "nunca"."""
    if segundos is None:
        return "nunca entrou"
    if segundos < 60:
        return "agora mesmo"
    if segundos < 3600:
        return f"há {segundos // 60} min"
    if segundos < 86400:
        horas = segundos // 3600
        return f"há {horas} h" if horas > 1 else "há 1 h"
    dias = segundos // 86400
    return f"há {dias} dias" if dias > 1 else "ontem"
