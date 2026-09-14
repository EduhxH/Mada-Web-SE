"""Ficheiros que o administrador carrega: imagens, GIFs, videos, foto de perfil.

Tres decisoes que sao a seguranca disto, e valem ser lidas antes do codigo.

**O nome do ficheiro que chega e ignorado.** Guarda-se com o nome
`<sha256 dos primeiros 16 bytes do resumo>.<extensao>`. Nao ha nenhum caminho
escolhido por quem carrega, portanto nao existe travessia de directorio para
tentar: nao ha `..`, nao ha barras, nao ha nomes reservados do Windows, e nao ha
o problema de um segundo ficheiro com o mesmo nome apagar o primeiro. De borla,
carregar duas vezes a mesma imagem nao a duplica em disco.

**A extensao tem de concordar com os primeiros bytes.** Aceitar um `.png` e
servi-lo como `image/png` e uma promessa ao browser; se o conteudo for HTML, a
promessa era falsa. O `X-Content-Type-Options: nosniff` que o servidor manda ja
impedia o browser de o executar, mas depender de um cabecalho para o que se pode
verificar no momento de guardar e depender do lado errado.

**SVG nao entra.** E o unico formato de imagem que e um documento: leva
`<script>` dentro e o browser executa-o no contexto desta origem. Um GIF nao faz
isso. Como a lista e de permissao e nao de recusa, o SVG fica de fora por nao
estar la - o que e mais seguro do que uma regra a diz-lo.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

PASTA = Path("data") / "media"
PASTA_PERFIL = Path("data") / "perfil"

CRLF = bytes.fromhex("0d0a")
CRLF2 = CRLF + CRLF

# Extensao -> (tipo servido, familia, assinaturas, limite em bytes).
#
# `assinaturas` e uma lista de ALTERNATIVAS, e cada alternativa e uma lista de
# marcas `(deslocamento, bytes)` que tem de bater todas. A distincao nao e
# academica: um GIF e "GIF87a" **ou** "GIF89a" no inicio, enquanto um WebP e
# "RIFF" no inicio **e** "WEBP" no oitavo byte. Quando isto era uma lista so,
# com um `all()` por cima, exigia-se que um GIF fosse as duas versoes ao mesmo
# tempo - e nenhum GIF passava. Apanhado por um teste, nao a olho.
_MEGA = 1024 * 1024
IMAGEM = "imagem"
VIDEO = "video"

_FORMATOS: dict[str, dict] = {
    "png": {
        "tipo": "image/png",
        "familia": IMAGEM,
        "assinaturas": [[(0, bytes.fromhex("89504e470d0a1a0a"))]],
        "limite": 6 * _MEGA,
    },
    "jpg": {
        "tipo": "image/jpeg",
        "familia": IMAGEM,
        "assinaturas": [[(0, bytes.fromhex("ffd8ff"))]],
        "limite": 6 * _MEGA,
    },
    "jpeg": {
        "tipo": "image/jpeg",
        "familia": IMAGEM,
        "assinaturas": [[(0, bytes.fromhex("ffd8ff"))]],
        "limite": 6 * _MEGA,
    },
    "gif": {
        "tipo": "image/gif",
        "familia": IMAGEM,
        # Duas versoes do formato, nunca as duas ao mesmo tempo.
        "assinaturas": [[(0, b"GIF87a")], [(0, b"GIF89a")]],
        "limite": 12 * _MEGA,
    },
    "webp": {
        "tipo": "image/webp",
        "familia": IMAGEM,
        # Uma alternativa so, com duas marcas: RIFF no inicio e WEBP no oitavo
        # byte. O tamanho do ficheiro fica pelo meio, e e por isso que sao duas.
        "assinaturas": [[(0, b"RIFF"), (8, b"WEBP")]],
        "limite": 6 * _MEGA,
    },
    "mp4": {
        "tipo": "video/mp4",
        "familia": VIDEO,
        "assinaturas": [[(4, b"ftyp")]],
        "limite": 40 * _MEGA,
    },
    "webm": {
        "tipo": "video/webm",
        "familia": VIDEO,
        "assinaturas": [[(0, bytes.fromhex("1a45dfa3"))]],
        "limite": 40 * _MEGA,
    },
}

EXTENSOES_IMAGEM = tuple(
    e for e, d in _FORMATOS.items() if d["familia"] == IMAGEM
)
EXTENSOES_VIDEO = tuple(e for e, d in _FORMATOS.items() if d["familia"] == VIDEO)

# O maior limite de todos, mais folga para os cabecalhos do multipart. Serve
# para o servidor saber quanto pode ler do socket antes de desistir: sem um
# tecto, um corpo anunciado com um Content-Length enorme era lido inteiro para
# memoria antes de alguem verificar se valia a pena.
LIMITE_CORPO = max(d["limite"] for d in _FORMATOS.values()) + 2 * _MEGA

LIMITE_PERFIL = 3 * _MEGA
# Sem video na foto de perfil: e um retrato ao lado de um nome.
EXTENSOES_PERFIL = EXTENSOES_IMAGEM


@dataclass
class Carregado:
    """Um ficheiro que veio num formulario multipart."""

    campo: str
    nome: str
    dados: bytes

    @property
    def extensao(self) -> str:
        return self.nome.rsplit(".", 1)[-1].lower() if "." in self.nome else ""


def _cabecalhos_da_parte(bruto: bytes) -> dict[str, str]:
    cabecalhos: dict[str, str] = {}
    for linha in bruto.decode("utf-8", errors="replace").split(CRLF.decode()):
        if ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        cabecalhos[chave.strip().lower()] = valor.strip()
    return cabecalhos


def _valor_do_parametro(cabecalho: str, nome: str) -> str:
    """Tira `filename="x.png"` de um Content-Disposition, sem as aspas."""
    for pedaco in cabecalho.split(";"):
        pedaco = pedaco.strip()
        if not pedaco.lower().startswith(nome.lower() + "="):
            continue
        valor = pedaco.split("=", 1)[1].strip()
        if valor.startswith('"') and valor.endswith('"') and len(valor) >= 2:
            valor = valor[1:-1]
        return valor
    return ""


def limite_do_multipart(tipo_conteudo: str) -> bytes:
    """O delimitador anunciado no Content-Type, em bytes."""
    fronteira = _valor_do_parametro(tipo_conteudo or "", "boundary")
    return fronteira.encode("utf-8", errors="replace") if fronteira else b""


def analisar_multipart(
    corpo: bytes, tipo_conteudo: str
) -> tuple[dict[str, str], list[Carregado]]:
    """Reparte um corpo `multipart/form-data` em campos de texto e ficheiros.

    Escrito a mao porque a alternativa da biblioteca padrao (`cgi.FieldStorage`)
    esta depreciada e sai na 3.13, e trazer uma dependencia so para isto ia
    contra a linha do projeto. O formato e simples: um delimitador entre partes,
    cabecalhos e corpo separados por uma linha em branco.

    Nao levanta em nenhuma entrada: um corpo truncado, um delimitador errado ou
    lixo binario devolvem o que se conseguiu ler. Quem chama trata o vazio.
    """
    fronteira = limite_do_multipart(tipo_conteudo)
    campos: dict[str, str] = {}
    ficheiros: list[Carregado] = []
    if not fronteira or not corpo:
        return campos, ficheiros

    separador = b"--" + fronteira
    for parte in corpo.split(separador):
        if not parte or parte.startswith(b"--"):
            # A ultima parte e "--" mais o que o cliente quiser; a primeira e
            # vazia. Nenhuma das duas traz dados.
            continue
        parte = parte.lstrip(CRLF)
        if CRLF2 not in parte:
            continue
        bruto, conteudo = parte.split(CRLF2, 1)
        # O delimitador seguinte vem precedido de CRLF, que pertence a sintaxe e
        # nao aos dados: sem o tirar, cada ficheiro guardado ficava dois bytes
        # maior do que o original.
        if conteudo.endswith(CRLF):
            conteudo = conteudo[: -len(CRLF)]

        cabecalhos = _cabecalhos_da_parte(bruto)
        disposicao = cabecalhos.get("content-disposition", "")
        nome_campo = _valor_do_parametro(disposicao, "name")
        if not nome_campo:
            continue
        # A presenca do parametro decide se e ficheiro, nao o seu valor. Um
        # `<input type=file>` deixado vazio manda `filename=""`, e tratar isso
        # como campo de texto punha um `media: ""` entre os campos - que depois
        # sobrescrevia um valor com o mesmo nome.
        if "filename=" in disposicao.lower():
            nome_ficheiro = _valor_do_parametro(disposicao, "filename")
            if nome_ficheiro and conteudo:
                ficheiros.append(Carregado(nome_campo, nome_ficheiro, conteudo))
            continue
        campos[nome_campo] = conteudo.decode("utf-8", errors="replace")
    return campos, ficheiros


def _assinatura_bate(dados: bytes, extensao: str) -> bool:
    """Uma das alternativas tem de bater, e nessa tem de bater tudo."""
    return any(
        all(
            dados[desloc : desloc + len(marca)] == marca
            for desloc, marca in alternativa
        )
        for alternativa in _FORMATOS[extensao]["assinaturas"]
    )


def validar(
    ficheiro: Carregado, permitidas: tuple[str, ...] | None = None,
    limite_extra: int | None = None,
) -> str:
    """Devolve o motivo da recusa, ou "" se esta bem."""
    extensao = ficheiro.extensao
    aceitas = permitidas if permitidas is not None else tuple(_FORMATOS)
    if extensao not in aceitas:
        return (
            f"formato não aceito ({extensao or 'sem extensão'});"
            f" aceito: {', '.join(sorted(aceitas))}"
        )
    limite = limite_extra or _FORMATOS[extensao]["limite"]
    if len(ficheiro.dados) > limite:
        return (
            f"{len(ficheiro.dados) / _MEGA:.1f} MB é demasiado"
            f" (máximo {limite // _MEGA} MB)"
        )
    if not _assinatura_bate(ficheiro.dados, extensao):
        return f"o conteúdo não é um {extensao} de verdade"
    return ""


def _nome_estavel(dados: bytes, extensao: str) -> str:
    return hashlib.sha256(dados).hexdigest()[:16] + "." + extensao


def guardar(ficheiro: Carregado, permitidas: tuple[str, ...] | None = None) -> tuple[str, str]:
    """Guarda em `data/media/`. Devolve `(nome, erro)`; um deles esta vazio."""
    motivo = validar(ficheiro, permitidas)
    if motivo:
        return "", motivo
    nome = _nome_estavel(ficheiro.dados, ficheiro.extensao)
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        (PASTA / nome).write_bytes(ficheiro.dados)
    except OSError as erro:
        return "", f"não consegui guardar: {erro}"
    return nome, ""


def guardar_perfil(rotulo: str, ficheiro: Carregado) -> tuple[str, str]:
    """A foto de um participante. Um ficheiro por rotulo, substituido.

    O nome vem do rotulo e nao do resumo do conteudo: o que se quer aqui e "a
    foto do admin-01", e a anterior deve desaparecer quando se troca - senao
    ficavam fotos antigas em disco para sempre.
    """
    motivo = validar(ficheiro, EXTENSOES_PERFIL, LIMITE_PERFIL)
    if motivo:
        return "", motivo
    seguro = "".join(c for c in rotulo if c.isalnum() or c in "-_")[:40]
    if not seguro:
        return "", "rótulo inválido"
    nome = f"{seguro}.{ficheiro.extensao}"
    try:
        PASTA_PERFIL.mkdir(parents=True, exist_ok=True)
        for antigo in PASTA_PERFIL.glob(f"{seguro}.*"):
            if antigo.name != nome:
                antigo.unlink(missing_ok=True)
        (PASTA_PERFIL / nome).write_bytes(ficheiro.dados)
    except OSError as erro:
        return "", f"não consegui guardar: {erro}"
    return nome, ""


def perfil_de(rotulo: str) -> str:
    """O nome do ficheiro da foto deste participante, ou "" se nao tem."""
    seguro = "".join(c for c in rotulo if c.isalnum() or c in "-_")[:40]
    if not seguro or not PASTA_PERFIL.exists():
        return ""
    for extensao in EXTENSOES_PERFIL:
        if (PASTA_PERFIL / f"{seguro}.{extensao}").exists():
            return f"{seguro}.{extensao}"
    return ""


def _nome_seguro(nome: str) -> str:
    """Aceita so o que esta funcao produz: resumo hexadecimal ou rotulo, e extensao.

    Isto e o portao de leitura. Nao ha aqui `os.path.join` com texto de fora: se
    o nome nao corresponder exactamente ao padrao, nao se chega a tocar no disco.
    """
    if "/" in nome or chr(92) in nome or ".." in nome:
        return ""
    if nome.count(".") != 1:
        return ""
    base, extensao = nome.rsplit(".", 1)
    extensao = extensao.lower()
    if extensao not in _FORMATOS:
        return ""
    if not base or not all(c.isalnum() or c in "-_" for c in base):
        return ""
    return f"{base}.{extensao}"


def tipo_de(nome: str) -> str:
    extensao = nome.rsplit(".", 1)[-1].lower()
    formato = _FORMATOS.get(extensao)
    return formato["tipo"] if formato else "application/octet-stream"


def familia_de(nome: str) -> str:
    extensao = nome.rsplit(".", 1)[-1].lower()
    formato = _FORMATOS.get(extensao)
    return formato["familia"] if formato else ""


def ler(nome: str, pasta: Path | None = None) -> tuple[bytes, str]:
    """Os bytes e o tipo de um ficheiro guardado. `(b"", "")` se nao serve."""
    seguro = _nome_seguro(nome)
    if not seguro:
        return b"", ""
    alvo = (pasta or PASTA) / seguro
    try:
        return alvo.read_bytes(), tipo_de(seguro)
    except OSError:
        return b"", ""


def listar() -> list[dict]:
    """O que esta na biblioteca, do mais recente para o mais antigo."""
    if not PASTA.exists():
        return []
    itens = []
    for alvo in PASTA.iterdir():
        if not alvo.is_file() or not _nome_seguro(alvo.name):
            continue
        try:
            estado = alvo.stat()
        except OSError:
            continue
        itens.append(
            {
                "nome": alvo.name,
                "url": f"/media/{alvo.name}",
                "familia": familia_de(alvo.name),
                "bytes": estado.st_size,
                "quando": estado.st_mtime,
            }
        )
    return sorted(itens, key=lambda i: -i["quando"])


def apagar(nome: str) -> bool:
    seguro = _nome_seguro(nome)
    if not seguro:
        return False
    try:
        (PASTA / seguro).unlink()
        return True
    except OSError:
        return False


def marcacao_de(nome: str) -> str:
    """A marcacao a inserir no post para mostrar este ficheiro."""
    if familia_de(nome) == VIDEO:
        return f"!video(/media/{nome})"
    return f"![](/media/{nome})"


def limites() -> dict[str, int]:
    """Extensao -> bytes aceitos. Vai para o formulario, para o browser avisar.

    O servidor recusa um corpo grande demais pelo `Content-Length`, antes de o
    ler - e a defesa certa, mas do lado de quem esta a carregar parece uma falha
    de rede: a ligacao fecha-se a meio do envio e nao chega resposta nenhuma
    para mostrar. Levar os limites ao browser evita a subida inteira e diz o que
    se passa antes de comecar.
    """
    return {extensao: dados["limite"] for extensao, dados in _FORMATOS.items()}


def legivel(quantos: int) -> str:
    if quantos < 1024:
        return f"{quantos} B"
    if quantos < _MEGA:
        return f"{quantos / 1024:.0f} KB"
    return f"{quantos / _MEGA:.1f} MB"
