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
CAMINHO_CORTES = Path("data") / "sessoes-cortadas.json"
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
    global _cache_rotulos
    CAMINHO_PARTICIPANTES.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_PARTICIPANTES.write_text(
        json.dumps(participantes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    _cache_rotulos = None


def proximo_numero(participantes: dict[str, str], prefixo: str) -> int:
    """O numero seguinte dentro deste prefixo, nao no ficheiro todo.

    Contar o ficheiro inteiro dava rotulos como `admin-06` quando ja havia
    cinco alunos: o numero passava a dizer a ordem em que os codigos foram
    criados, e nao quem era a pessoa. Um rotulo e para ler em voz alta numa
    sala - "aluno-03" - por isso conta-se cada familia por si.
    """
    marca = f"{prefixo}-"
    usados = [
        int(rotulo[len(marca):])
        for rotulo in participantes.values()
        if rotulo.startswith(marca) and rotulo[len(marca):].isdigit()
    ]
    return max(usados, default=0) + 1


def criar_participantes(quantos: int, prefixo: str = "aluno") -> dict[str, str]:
    participantes = carregar_participantes()
    primeiro = proximo_numero(participantes, prefixo)
    novos: dict[str, str] = {}
    for numero in range(primeiro, primeiro + quantos):
        codigo = gerar_codigo()
        rotulo = f"{prefixo}-{numero:02d}"
        participantes[impressao(codigo)] = rotulo
        novos[codigo] = rotulo
    guardar_participantes(participantes)
    return novos


def zerar_participantes() -> int:
    """Apaga todos os codigos. Devolve quantos sairam.

    Serve para comecar um piloto sem arrastar os codigos de teste: eles
    continuariam a funcionar, e um codigo que anda em capturas de ecra e
    ficheiros de apontamentos nao e um codigo.
    """
    participantes = carregar_participantes()
    quantos = len(participantes)
    # Cortar cada rotulo antes de os apagar. Sem isto, criar `aluno-01` outra
    # vez fazia o cookie do `aluno-01` anterior voltar a valer - o rotulo e o
    # mesmo e a lista de ativos nao distingue as duas pessoas. Era o buraco que
    # me obrigou a trocar o segredo de assinatura a mao.
    for rotulo in set(participantes.values()):
        cortar_sessoes(rotulo)
    guardar_participantes({})
    return quantos


def revogar(rotulo: str) -> bool:
    participantes = carregar_participantes()
    restantes = {h: r for h, r in participantes.items() if r != rotulo}
    if len(restantes) == len(participantes):
        return False
    guardar_participantes(restantes)
    # Tirar o rotulo da lista ja fecha a porta. O corte e para o caso de o
    # rotulo voltar a existir mais tarde - `aluno-03` recriado nao pode herdar
    # a sessao do `aluno-03` de antes, que era outra pessoa.
    cortar_sessoes(rotulo)
    return True


def novo_codigo(rotulo: str) -> str | None:
    """Troca o codigo de quem ja existe, mantendo o rotulo. None se nao existe.

    O rotulo sobrevive de proposito: o historico de uso esta ligado a ele, e
    quem perdeu o papel do codigo continua a ser a mesma pessoa da turma. O que
    nao sobrevive e a sessao aberta - ver `cortar_sessoes`.
    """
    participantes = carregar_participantes()
    if rotulo not in participantes.values():
        return None
    codigo = gerar_codigo()
    restantes = {h: r for h, r in participantes.items() if r != rotulo}
    restantes[impressao(codigo)] = rotulo
    guardar_participantes(restantes)
    cortar_sessoes(rotulo)
    return codigo


_cache_epocas: tuple[object, dict[str, int]] | None = None


def _epocas() -> dict[str, int]:
    """Quantas vezes as sessoes de cada rotulo foram cortadas.

    Em cache pela marca do ficheiro, como os rotulos ativos: isto e consultado a
    cada pedido autenticado e nao pode custar uma leitura de disco por busca.
    """
    global _cache_epocas
    try:
        estado = CAMINHO_CORTES.stat()
        marca: object = (estado.st_mtime_ns, estado.st_size)
    except OSError:
        marca = None
    if _cache_epocas is not None and _cache_epocas[0] == marca:
        return _cache_epocas[1]

    lidas: dict[str, int] = {}
    if CAMINHO_CORTES.exists():
        try:
            dados = json.loads(CAMINHO_CORTES.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                lidas = {
                    str(k): int(v)
                    for k, v in dados.items()
                    if isinstance(v, int) or str(v).isdigit()
                }
        except (json.JSONDecodeError, OSError, ValueError):
            lidas = {}
    _cache_epocas = (marca, lidas)
    return lidas


def epoca_de(rotulo: str) -> int:
    return _epocas().get(rotulo, 0)


def cortar_sessoes(rotulo: str) -> int:
    """Invalida as sessoes ja abertas deste participante. Devolve a epoca nova.

    Sem isto, "gerar novo codigo" nao expulsava ninguem: o rotulo continua a
    existir, portanto o cookie antigo continuava a passar a verificacao. E o
    motivo para gerar um codigo novo e muitas vezes o contrario - o codigo andou
    por onde nao devia, e quem o usou tem de sair.

    E um contador e nao um instante de propósito. Com um carimbo de tempo havia
    sempre um segundo de ambiguidade (a sessao guarda a emissao ao segundo), e
    esse segundo tinha de ser resolvido a favor de alguem: ou uma sessao
    comprometida sobrevivia, ou uma entrada legitima era recusada. Um contador
    nao tem lados - a sessao ou traz a epoca em vigor ou nao traz.
    """
    global _cache_epocas
    epocas = dict(_epocas())
    epocas[rotulo] = epocas.get(rotulo, 0) + 1
    CAMINHO_CORTES.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_CORTES.write_text(
        json.dumps(epocas, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    _cache_epocas = None
    return epocas[rotulo]


def _assinar(corpo: str, chave: bytes) -> str:
    return hmac.new(chave, corpo.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def criar_sessao(participante: str, chave: bytes) -> str:
    """`participante|epoca|emitido|assinatura`, assinado com HMAC.

    A epoca vai dentro do que e assinado: nao se pode mexer nela do lado do
    cliente, e e ela que permite expulsar uma pessoa sem trocar o segredo da
    maquina (o que expulsaria a turma toda e invalidaria todos os codigos).
    """
    corpo = f"{participante}|{epoca_de(participante)}|{int(time.time())}"
    return f"{corpo}|{_assinar(corpo, chave)}"


def _abrir_sessao(valor: str, chave: bytes) -> tuple[str, int] | None:
    """(participante, epoca) se a assinatura e a idade batem. None se nao."""
    partes = valor.split("|")
    if len(partes) != 4:
        return None
    participante, epoca, emitido, assinatura = partes
    corpo = f"{participante}|{epoca}|{emitido}"
    if not hmac.compare_digest(assinatura, _assinar(corpo, chave)):
        return None
    try:
        nascimento = int(emitido)
        numero = int(epoca)
    except ValueError:
        return None
    idade = time.time() - nascimento
    if idade > VALIDADE_DIAS * 86400 or idade < -3600:
        return None
    return participante, numero


def validar_sessao(valor: str, chave: bytes) -> str | None:
    """So a verificacao criptografica: assinatura boa e dentro do prazo.

    Nao pergunta se o participante ainda existe - para isso e que ha
    `participante_da_sessao`, e e essa que a barreira do servidor usa. As duas
    coisas tem nomes diferentes de proposito: foi confundi-las que fez
    `--revogar` nao revogar nada durante trinta dias.
    """
    aberta = _abrir_sessao(valor, chave)
    return aberta[0] if aberta else None


_cache_rotulos: tuple[object, frozenset[str]] | None = None


def rotulos_ativos() -> frozenset[str]:
    """Os rotulos que ainda tem codigo valido.

    Consultado a cada pedido, portanto nao pode ler e interpretar o JSON todas
    as vezes. A chave da cache e (mtime, tamanho) do ficheiro: reescreve-lo
    muda sempre um dos dois, e um `guardar_participantes` no mesmo processo
    limpa a cache diretamente - o mtime do Windows podia nao ter resolucao
    suficiente para dois acertos no mesmo segundo.
    """
    global _cache_rotulos
    try:
        estado = CAMINHO_PARTICIPANTES.stat()
        marca: object = (estado.st_mtime_ns, estado.st_size)
    except OSError:
        marca = None
    if _cache_rotulos is not None and _cache_rotulos[0] == marca:
        return _cache_rotulos[1]
    rotulos = frozenset(carregar_participantes().values())
    _cache_rotulos = (marca, rotulos)
    return rotulos


def participante_da_sessao(valor: str, chave: bytes) -> str | None:
    """Como `validar_sessao`, mas recusa quem ja nao tem codigo.

    Sem isto, `--revogar` nao revogava nada durante trinta dias. A assinatura
    do cookie continua boa depois de o codigo desaparecer - e era so a
    assinatura que se verificava. Quem tivesse entrado uma vez ficava dentro,
    e um `admin-` revogado continuava a ver as estatisticas da turma inteira.

    Pior do que isso, e o que me fez ir a procurar: apagar os participantes e
    criar outros com os mesmos rotulos nao expulsava ninguem. O cookie do
    `aluno-01` antigo passava a valer para o `aluno-01` novo, e as buscas de
    um ficavam no registo do outro.
    """
    aberta = _abrir_sessao(valor, chave)
    if aberta is None:
        return None
    participante, epoca = aberta
    if participante not in rotulos_ativos():
        return None
    if epoca != epoca_de(participante):
        return None
    return participante


def simbolo_csrf(participante: str) -> str:
    """Um valor que so este servidor sabe calcular, preso ao participante.

    O cookie de sessao ja vai com `SameSite=Lax`, o que impede o browser de o
    mandar num POST vindo de outro sitio - portanto isto e a segunda linha e nao
    a primeira. Vale a pena tendo em conta o que os formularios do painel fazem:
    revogar acessos e apagar posts nao sao coisas para depender de uma so
    defesa, e um browser antigo que ignore o `SameSite` passa a estar coberto.

    Nao muda a cada formulario. Mudava se houvesse forma de guardar estado por
    formulario sem sessao do lado do servidor, e nao ha - o que este simbolo tem
    de garantir e que quem faz o pedido conhece o segredo da maquina, e isso
    garante.
    """
    return hmac.new(
        segredo(), f"csrf|{participante}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def csrf_valido(participante: str | None, simbolo: str | None) -> bool:
    if not participante or not simbolo:
        return False
    return hmac.compare_digest(simbolo, simbolo_csrf(participante))


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
