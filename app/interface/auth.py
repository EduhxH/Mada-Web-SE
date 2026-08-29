import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

CAMINHO_ENV = Path(".env")
CAMINHO_SEGREDO = Path("data") / "segredo.txt"
CAMINHO_PARTICIPANTES = Path("data") / "participantes.json"
VAR_SEGREDO = "MADALENA_SEGREDO"
NOME_COOKIE = "madalena"
VALIDADE_DIAS = 30
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PADRAO_CODIGO = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
# Participantes cujo rotulo comeca assim veem as estatisticas completas.
PREFIXO_ADMIN = "admin"

_env_carregado = False


def carregar_env(caminho: Path | None = None) -> None:
    global _env_carregado
    caminho = caminho if caminho is not None else CAMINHO_ENV
    if _env_carregado or not caminho.exists():
        _env_carregado = True
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))
    _env_carregado = True


def segredo() -> bytes:
    carregar_env()
    do_ambiente = os.environ.get(VAR_SEGREDO)
    if do_ambiente:
        return do_ambiente.encode("utf-8")
    if CAMINHO_SEGREDO.exists():
        return CAMINHO_SEGREDO.read_bytes()
    CAMINHO_SEGREDO.parent.mkdir(parents=True, exist_ok=True)
    novo = secrets.token_bytes(32)
    CAMINHO_SEGREDO.write_bytes(novo)
    return novo


def gerar_codigo() -> str:
    parte = lambda: "".join(secrets.choice(ALFABETO) for _ in range(4))
    return f"{parte()}-{parte()}"


def impressao(codigo: str, chave: bytes | None = None) -> str:
    chave = chave if chave is not None else segredo()
    normalizado = codigo.strip().upper().replace(" ", "")
    return hmac.new(chave, normalizado.encode("utf-8"), hashlib.sha256).hexdigest()


def carregar_participantes() -> dict[str, str]:
    if not CAMINHO_PARTICIPANTES.exists():
        return {}
    try:
        dados = json.loads(CAMINHO_PARTICIPANTES.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return _migrar_claros(dados)


def _migrar_claros(dados: dict[str, str]) -> dict[str, str]:
    claros = [chave for chave in dados if PADRAO_CODIGO.match(chave)]
    if not claros:
        return dados
    migrado = {
        (impressao(chave) if chave in claros else chave): rotulo
        for chave, rotulo in dados.items()
    }
    guardar_participantes(migrado)
    return migrado


def guardar_participantes(participantes: dict[str, str]) -> None:
    CAMINHO_PARTICIPANTES.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_PARTICIPANTES.write_text(
        json.dumps(participantes, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def criar_participantes(quantos: int, prefixo: str = "aluno") -> dict[str, str]:
    participantes = carregar_participantes()
    existentes = len(participantes)
    novos: dict[str, str] = {}
    for numero in range(existentes + 1, existentes + quantos + 1):
        codigo = gerar_codigo()
        rotulo = f"{prefixo}-{numero:02d}"
        participantes[impressao(codigo)] = rotulo
        novos[codigo] = rotulo
    guardar_participantes(participantes)
    return novos


def revogar(rotulo: str) -> bool:
    participantes = carregar_participantes()
    restantes = {h: r for h, r in participantes.items() if r != rotulo}
    if len(restantes) == len(participantes):
        return False
    guardar_participantes(restantes)
    return True


def _assinar(corpo: str, chave: bytes) -> str:
    return hmac.new(chave, corpo.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def criar_sessao(participante: str, chave: bytes) -> str:
    corpo = f"{participante}|{int(time.time())}"
    return f"{corpo}|{_assinar(corpo, chave)}"


def validar_sessao(valor: str, chave: bytes) -> str | None:
    partes = valor.split("|")
    if len(partes) != 3:
        return None
    participante, emitido, assinatura = partes
    corpo = f"{participante}|{emitido}"
    if not hmac.compare_digest(assinatura, _assinar(corpo, chave)):
        return None
    try:
        idade = time.time() - int(emitido)
    except ValueError:
        return None
    if idade > VALIDADE_DIAS * 86400 or idade < -3600:
        return None
    return participante


def e_administrador(rotulo: str | None) -> bool:
    return bool(rotulo) and rotulo.startswith(PREFIXO_ADMIN)


def participante_do_codigo(codigo: str) -> str | None:
    if not codigo.strip():
        return None
    alvo = impressao(codigo)
    for guardado, rotulo in carregar_participantes().items():
        if hmac.compare_digest(guardado, alvo):
            return rotulo
    return None
