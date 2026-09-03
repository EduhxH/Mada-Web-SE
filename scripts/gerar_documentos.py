"""Gera os PDFs dos documentos publicos, com a marca do Madalena.

**Escrito a mao, sem biblioteca de PDF.** Nao ha reportlab nem weasyprint no
projeto e nao vale a pena acrescenta-los por dois documentos: um PDF de texto
e um formato simples de escrever, e assim os ficheiros ficam com texto
seleccionavel (importa para quem copia, para leitores de ecra e para procurar
la dentro), com poucos kilobytes, e sem mais uma dependencia para manter.

Duas decisoes que poupam trabalho:

- **Fontes base-14.** Helvetica e Times fazem parte do proprio formato: nao ha
  ficheiro para embeber. Com `WinAnsiEncoding` cobrem os acentos portugueses
  todos, que e o que aqui interessa.
- **O logotipo entra composto sobre branco.** O PNG tem transparencia, e
  imagens com canal alfa em PDF obrigam a uma mascara separada. Como a pagina
  e branca, achatar contra branco da exactamente o mesmo resultado por
  metade do trabalho.

Correr com:  python scripts/gerar_documentos.py
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOGOTIPO = RAIZ / "assets" / "marca" / "logo.png"
DESTINO = RAIZ / "assets" / "documentos"

# A4 em pontos (1/72 de polegada), que e a unidade nativa do PDF.
LARGURA, ALTURA = 595.28, 841.89
MARGEM = 62.0
TOPO = ALTURA - 78.0
BASE = 68.0

# --- Quem responde pelos documentos. -----------------------------------
# Dois enderecos de proposito. O escolar vem primeiro em tudo o que e dirigido
# a alunos e a encarregados de educacao: e institucional, e verificavel contra
# a escola, e nao obriga ninguem a escrever para um endereco pessoal para
# exercer um direito. O outro fica como alternativa.
CONTACTO_ESCOLAR = "a2025016@alunos.sefo.pt"
CONTACTO_PESSOAL = "eduardo.carvalho.pt.dev@gmail.com"
CONTACTO = f"{CONTACTO_ESCOLAR} (ou {CONTACTO_PESSOAL})"
RESPONSAVEL = "Eduardo, aluno da turma PSI9 da ESCO"
VERSAO = "Vers\u00e3o 1 \u2014 setembro de 2026"

# Larguras dos caracteres da Helvetica, em milesimos de em. Sem isto nao ha
# como partir linhas: o PDF nao quebra texto, quem quebra e quem escreve.
_LARGURAS_HELVETICA = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 "
    "556 556 556 556 556 556 556 556 278 278 584 584 584 556 1015 667 667 722 "
    "722 667 611 778 722 278 500 667 556 833 722 778 667 778 722 667 611 722 "
    "667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 556 "
    "556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 "
    "500 334 260 334 584"
).split()


def _largura(texto: str, tamanho: float, negrito: bool = False) -> float:
    """Largura de uma linha em pontos.

    A Helvetica-Bold e cerca de 6% mais larga que a normal nos caracteres que
    aqui aparecem; aproximar por um fator evita carregar uma segunda tabela
    para o unico sitio onde faz diferenca, que e caber ou nao caber.
    """
    total = 0.0
    for c in texto:
        codigo = ord(c)
        if 32 <= codigo <= 126:
            total += int(_LARGURAS_HELVETICA[codigo - 32])
        else:
            # Acentuados e travessoes: a largura de um "o" e uma aproximacao
            # boa o suficiente para decidir quebras de linha.
            total += 556
    fator = 1.06 if negrito else 1.0
    return total / 1000.0 * tamanho * fator


def _pesar(texto: str) -> list[tuple[str, bool]]:
    saida: list[tuple[str, bool]] = []
    negrito = False
    for pedaco in re.split(r"(<b>|</b>)", texto):
        if pedaco == "<b>":
            negrito = True
        elif pedaco == "</b>":
            negrito = False
        elif pedaco:
            for palavra in pedaco.split():
                saida.append((palavra, negrito))
    return saida


def _quebrar_pesado(
    palavras: list[tuple[str, bool]], tamanho: float, largura: float
) -> list[list[tuple[str, bool]]]:
    linhas: list[list[tuple[str, bool]]] = []
    atual: list[tuple[str, bool]] = []
    largura_atual = 0.0
    espaco = _largura(" ", tamanho)
    for palavra, negrito in palavras:
        w = _largura(palavra, tamanho, negrito)
        precisa = w if not atual else largura_atual + espaco + w
        if atual and precisa > largura:
            linhas.append(atual)
            atual, largura_atual = [(palavra, negrito)], w
        else:
            atual.append((palavra, negrito))
            largura_atual = precisa
    if atual:
        linhas.append(atual)
    return linhas or [[]]


def _quebrar(texto: str, tamanho: float, largura: float, negrito=False) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if atual and _largura(tentativa, tamanho, negrito) > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas or [""]


def _texto_pdf(texto: str) -> bytes:
    """Escapa e codifica para dentro de um literal de string do PDF."""
    saida = texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return saida.encode("cp1252", errors="replace")


class Documento:
    """Um PDF de varias paginas, montado a medida que se escreve."""

    def __init__(self, titulo: str, subtitulo: str = ""):
        self.titulo = titulo
        self.subtitulo = subtitulo
        self.paginas: list[list[bytes]] = []
        self.fluxo: list[bytes] = []
        self.y = 0.0
        # caminho -> (nome no PDF, bytes comprimidos, largura, altura)
        self.imagens: dict[str, tuple[str, bytes, int, int]] = {}
        self._nova_pagina(primeira=True)

    def _registar(self, caminho: Path, largura_alvo: int) -> tuple[str, int, int]:
        """Prepara uma imagem para o PDF e devolve o nome por que e chamada.

        Cada imagem entra uma so vez, mesmo que apareca em varias paginas.
        """
        chave = str(caminho)
        if chave not in self.imagens:
            dados, largura, altura = _imagem_comprimida(caminho, largura_alvo)
            nome = f"Im{len(self.imagens) + 2}"  # Im1 e o logotipo
            self.imagens[chave] = (nome, dados, largura, altura)
        nome, _, largura, altura = self.imagens[chave]
        return nome, largura, altura

    # ---------------------------------------------------------------- base

    def _op(self, linha: str) -> None:
        self.fluxo.append(linha.encode("ascii"))

    def _escrever(self, texto: str, x: float, y: float, tamanho: float,
                  fonte: str = "F1", cinzento: float = 0.0) -> None:
        self._op(f"BT /{fonte} {tamanho:.1f} Tf {cinzento:.2f} g "
                 f"{x:.1f} {y:.1f} Td")
        self.fluxo.append(b"(" + _texto_pdf(texto) + b") Tj ET")

    def _escrever_pesado(self, linha, x: float, y: float, tamanho: float,
                         cinzento: float) -> None:
        """Uma linha com palavras normais e a negrito, lado a lado."""
        espaco = _largura(" ", tamanho)
        cursor = x
        indice = 0
        while indice < len(linha):
            negrito = linha[indice][1]
            grupo = []
            while indice < len(linha) and linha[indice][1] == negrito:
                grupo.append(linha[indice][0])
                indice += 1
            texto = " ".join(grupo)
            self._escrever(texto, cursor, y, tamanho,
                           "F2" if negrito else "F1", cinzento)
            cursor += _largura(texto, tamanho, negrito)
            if indice < len(linha):
                cursor += espaco

    def _nova_pagina(self, primeira: bool = False) -> None:
        if not primeira:
            self.paginas.append(self.fluxo)
        self.fluxo = []
        self.y = TOPO
        if primeira:
            self._cabecalho_capa()
        else:
            self._cabecalho_corrido()

    def _cabecalho_capa(self) -> None:
        # O logotipo ocupa 74 pontos de altura, no canto superior esquerdo.
        altura_logo = 74.0
        largura_logo = altura_logo * _proporcao_logo()
        self._op("q")
        self._op(f"{largura_logo:.1f} 0 0 {altura_logo:.1f} "
                 f"{MARGEM:.1f} {(ALTURA - 62 - altura_logo):.1f} cm /Im1 Do")
        self._op("Q")
        self.y = ALTURA - 62 - altura_logo - 34

        for linha in _quebrar(self.titulo, 21, LARGURA - 2 * MARGEM, True):
            self._escrever(linha, MARGEM, self.y, 21, "F2")
            self.y -= 26
        if self.subtitulo:
            self.y -= 2
            self._escrever(self.subtitulo, MARGEM, self.y, 9.5, "F1", 0.45)
            self.y -= 16
        self.y -= 8
        self._op(f"0.82 G 0.7 w {MARGEM:.1f} {self.y:.1f} m "
                 f"{(LARGURA - MARGEM):.1f} {self.y:.1f} l S")
        self.y -= 26

    def _cabecalho_corrido(self) -> None:
        altura_logo = 20.0
        largura_logo = altura_logo * _proporcao_logo()
        self._op("q")
        self._op(f"{largura_logo:.1f} 0 0 {altura_logo:.1f} "
                 f"{MARGEM:.1f} {(ALTURA - 52):.1f} cm /Im1 Do")
        self._op("Q")
        self._escrever(self.titulo, MARGEM + largura_logo + 10, ALTURA - 45,
                       8, "F1", 0.5)
        linha = ALTURA - 62
        self._op(f"0.88 G 0.6 w {MARGEM:.1f} {linha:.1f} m "
                 f"{(LARGURA - MARGEM):.1f} {linha:.1f} l S")
        self.y = linha - 30

    def _espaco(self, preciso: float) -> None:
        if self.y - preciso < BASE:
            self._nova_pagina()

    # -------------------------------------------------------------- blocos

    def titulo_seccao(self, texto: str) -> None:
        self._espaco(52)
        self.y -= 12
        self._escrever(texto, MARGEM, self.y, 12.5, "F2")
        self.y -= 19

    def paragrafo(self, texto: str, tamanho: float = 10, cinzento: float = 0.12,
                  recuo: float = 0.0) -> None:
        largura = LARGURA - 2 * MARGEM - recuo
        for linha in _quebrar_pesado(_pesar(texto), tamanho, largura):
            self._espaco(tamanho + 5)
            self._escrever_pesado(linha, MARGEM + recuo, self.y, tamanho, cinzento)
            self.y -= tamanho + 4.6
        self.y -= 6

    def item(self, texto: str) -> None:
        largura = LARGURA - 2 * MARGEM - 16
        linhas = _quebrar_pesado(_pesar(texto), 10, largura)
        for indice, linha in enumerate(linhas):
            self._espaco(15)
            if indice == 0:
                self._escrever("•", MARGEM + 3, self.y, 10, "F1", 0.45)
            self._escrever_pesado(linha, MARGEM + 16, self.y, 10, 0.12)
            self.y -= 14.6
        self.y -= 2

    def campo(self, nome: str, descricao: str, obrigatorio: bool = True) -> None:
        """Uma linha de formulario: nome a negrito, o que se escreve ao lado."""
        self._espaco(34)
        marca = " *" if obrigatorio else ""
        self._escrever(f"{nome}{marca}", MARGEM, self.y, 9.5, "F2")
        self.y -= 13
        for linha in _quebrar(descricao, 9, LARGURA - 2 * MARGEM - 12):
            self._espaco(13)
            self._escrever(linha, MARGEM + 12, self.y, 9, "F1", 0.42)
            self.y -= 12
        # a linha de escrita
        self.y -= 4
        self._op(f"0.75 G 0.6 w {(MARGEM + 12):.1f} {self.y:.1f} m "
                 f"{(LARGURA - MARGEM):.1f} {self.y:.1f} l S")
        self.y -= 20

    def imagem(self, caminho: Path, legenda: str = "",
               largura_max: float = 0.0) -> None:
        """Uma captura de ecra, com contorno fino e legenda por baixo.

        O contorno nao e enfeite: sem ele, uma captura de fundo claro impressa
        em papel branco nao tem onde acabar.
        """
        largura_col = LARGURA - 2 * MARGEM
        alvo = largura_max or largura_col
        nome, px_l, px_a = self._registar(caminho, int(alvo * 2))
        largura = min(alvo, largura_col)
        altura = largura * px_a / px_l

        # Uma captura nao se parte ao meio: se nao cabe, vai inteira para a
        # pagina seguinte.
        preciso = altura + (16 if legenda else 0) + 14
        if self.y - preciso < BASE:
            self._nova_pagina()

        topo = self.y - altura
        self._op("q")
        self._op(f"{largura:.1f} 0 0 {altura:.1f} {MARGEM:.1f} {topo:.1f} cm "
                 f"/{nome} Do")
        self._op("Q")
        self._op(f"0.78 G 0.5 w {MARGEM:.1f} {topo:.1f} {largura:.1f} "
                 f"{altura:.1f} re S")
        self.y = topo - 13
        if legenda:
            for linha in _quebrar(legenda, 8.5, largura_col):
                self._escrever(linha, MARGEM, self.y, 8.5, "F1", 0.45)
                self.y -= 11
        self.y -= 10

    def nota(self, texto: str) -> None:
        """Bloco recuado com barra a esquerda, para avisos."""
        largura = LARGURA - 2 * MARGEM - 20
        linhas = _quebrar_pesado(_pesar(texto), 9.5, largura)
        alto = len(linhas) * 13.4 + 10
        self._espaco(alto + 8)
        topo = self.y + 9
        self._op(f"0.35 G 1.6 w {MARGEM:.1f} {topo:.1f} m "
                 f"{MARGEM:.1f} {(topo - alto):.1f} l S")
        for linha in linhas:
            self._escrever_pesado(linha, MARGEM + 14, self.y, 9.5, 0.3)
            self.y -= 13.4
        self.y -= 10

    def separador(self) -> None:
        self._espaco(24)
        self.y -= 6
        self._op(f"0.88 G 0.6 w {MARGEM:.1f} {self.y:.1f} m "
                 f"{(LARGURA - MARGEM):.1f} {self.y:.1f} l S")
        self.y -= 18

    # ------------------------------------------------------------ montagem

    def guardar(self, caminho: Path) -> None:
        self.paginas.append(self.fluxo)
        imagem, largura_px, altura_px = _logotipo_comprimido()

        objetos: list[bytes] = []

        def junta(corpo: bytes) -> int:
            objetos.append(corpo)
            return len(objetos)

        # os rodapes so agora, que ja se sabe o total de paginas
        total = len(self.paginas)
        fluxos = []
        for numero, fluxo in enumerate(self.paginas, start=1):
            copia = list(fluxo)
            rodape = f"{VERSAO}   ·   Madalena Search   ·   {numero}/{total}"
            copia.append(
                b"BT /F1 7.5 Tf 0.55 g "
                + f"{MARGEM:.1f} {(BASE - 22):.1f} Td".encode("ascii")
                + b" (" + _texto_pdf(rodape) + b") Tj ET"
            )
            fluxos.append(b"\n".join(copia))

        ids_pagina = []
        id_fonte_n = junta(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                           b"/Encoding /WinAnsiEncoding >>")
        id_fonte_b = junta(b"<< /Type /Font /Subtype /Type1 "
                           b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        id_imagem = junta(
            b"<< /Type /XObject /Subtype /Image /Width "
            + str(largura_px).encode()
            + b" /Height " + str(altura_px).encode()
            + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode"
            b" /Length " + str(len(imagem)).encode() + b" >>\nstream\n"
            + imagem + b"\nendstream"
        )

        # O /Pages tem de conhecer os filhos e cada pagina tem de apontar para
        # o /Pages: um dos dois numeros tem de ser reservado antes de existir.
        # A partir daqui entram dois objetos por pagina (conteudo e pagina), e
        # o /Pages e o seguinte.
        # As capturas entram como objetos proprios, antes das paginas, para
        # que os ids ja existam quando cada pagina lista os seus recursos.
        xobjects = b"/Im1 " + str(id_imagem).encode() + b" 0 R"
        for nome, dados, largura_px, altura_px in self.imagens.values():
            id_extra = junta(
                b"<< /Type /XObject /Subtype /Image /Width "
                + str(largura_px).encode()
                + b" /Height " + str(altura_px).encode()
                + b" /ColorSpace /DeviceRGB /BitsPerComponent 8"
                b" /Filter /FlateDecode /Length " + str(len(dados)).encode()
                + b" >>\nstream\n" + dados + b"\nendstream"
            )
            xobjects += b" /" + nome.encode() + b" " + str(id_extra).encode() + b" 0 R"

        id_paginas = len(objetos) + 2 * len(fluxos) + 1
        for corpo in fluxos:
            comprimido = zlib.compress(corpo)
            id_conteudo = junta(
                b"<< /Length " + str(len(comprimido)).encode()
                + b" /Filter /FlateDecode >>\nstream\n" + comprimido + b"\nendstream"
            )
            ids_pagina.append(junta(
                b"<< /Type /Page /Parent " + str(id_paginas).encode()
                + b" 0 R /MediaBox [0 0 "
                + f"{LARGURA:.2f} {ALTURA:.2f}".encode()
                + b"] /Resources << /Font << /F1 " + str(id_fonte_n).encode()
                + b" 0 R /F2 " + str(id_fonte_b).encode()
                + b" 0 R >> /XObject << " + xobjects
                + b" >> >> /Contents " + str(id_conteudo).encode() + b" 0 R >>"
            ))

        filhos = b" ".join(f"{i} 0 R".encode() for i in ids_pagina)
        id_real_paginas = junta(
            b"<< /Type /Pages /Count " + str(len(ids_pagina)).encode()
            + b" /Kids [" + filhos + b"] >>"
        )
        assert id_real_paginas == id_paginas, "reserva do id de /Pages saiu errada"

        id_info = junta(
            b"<< /Title (" + _texto_pdf(self.titulo) + b") "
            b"/Author (Madalena Search) /Creator (Madalena Search) >>"
        )
        id_raiz = junta(
            b"<< /Type /Catalog /Pages " + str(id_real_paginas).encode() + b" 0 R >>"
        )

        saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posicoes = []
        for numero, corpo in enumerate(objetos, start=1):
            posicoes.append(len(saida))
            saida += str(numero).encode() + b" 0 obj\n" + corpo + b"\nendobj\n"

        inicio_tabela = len(saida)
        saida += b"xref\n0 " + str(len(objetos) + 1).encode() + b"\n"
        saida += b"0000000000 65535 f \n"
        for posicao in posicoes:
            saida += f"{posicao:010d} 00000 n \n".encode()
        saida += (
            b"trailer\n<< /Size " + str(len(objetos) + 1).encode()
            + b" /Root " + str(id_raiz).encode() + b" 0 R"
            + b" /Info " + str(id_info).encode() + b" 0 R >>\n"
            b"startxref\n" + str(inicio_tabela).encode() + b"\n%%EOF\n"
        )
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(bytes(saida))


def _imagem_comprimida(caminho: Path, largura_alvo: int) -> tuple[bytes, int, int]:
    """Reduz uma imagem e devolve os pixeis prontos para o PDF.

    Reduzir antes de embeber e o que decide o tamanho do ficheiro: uma captura
    a 2800px de largura seriam oito megabytes de pixeis por imagem. A largura
    alvo e o dobro da largura em pontos na pagina, o que da cerca de 144 pontos
    por polegada - suficiente para imprimir sem se ver o pixel.
    """
    from PIL import Image

    imagem = Image.open(caminho).convert("RGB")
    if imagem.width > largura_alvo:
        altura = round(imagem.height * largura_alvo / imagem.width)
        imagem = imagem.resize((largura_alvo, altura), Image.LANCZOS)
    return zlib.compress(imagem.tobytes(), 9), imagem.width, imagem.height


_cache_logo: tuple[bytes, int, int] | None = None


def _logotipo_comprimido() -> tuple[bytes, int, int]:
    global _cache_logo
    if _cache_logo is None:
        from PIL import Image

        imagem = Image.open(LOGOTIPO).convert("RGBA")
        # Reduzir antes de embeber: a 300 pontos de largura chega para
        # impressao e corta o ficheiro para um quinto.
        imagem.thumbnail((300, 300), Image.LANCZOS)
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        fundo.paste(imagem, mask=imagem.split()[3])
        _cache_logo = (zlib.compress(fundo.tobytes(), 9), *fundo.size)
    return _cache_logo


def _proporcao_logo() -> float:
    _, largura, altura = _logotipo_comprimido()
    return largura / altura


# ======================================================================
#  Os documentos
# ======================================================================

def politica_privacidade() -> Documento:
    d = Documento(
        "Política de Privacidade e Cookies",
        "Madalena Search \u2014 motor de busca do material da ESCO",
    )

    d.nota(
        "Este documento descreve o que o Madalena regista, porque o faz e durante "
        "quanto tempo. Está escrito para ser lido por alunos e encarregados de "
        "educação, e não por juristas."
    )

    d.titulo_seccao("1. Quem trata os teus dados")
    d.paragrafo(
        f"O Madalena é um projeto escolar desenvolvido por {RESPONSAVEL}. Neste "
        "momento é um piloto fechado, com um número reduzido de participantes "
        "convidados, e não está aberto ao público."
    )
    d.paragrafo(f"Para qualquer questão sobre este documento: {CONTACTO}.")

    d.titulo_seccao("2. O que fica registado quando pesquisas")
    d.paragrafo(
        "Sempre que fazes uma pesquisa ou abres um documento, o Madalena guarda "
        "uma linha com:"
    )
    d.item("o rótulo que te foi atribuído (aluno-01, aluno-02, ...);")
    d.item("a data e a hora, ao segundo;")
    d.item("o texto que escreveste na caixa de pesquisa;")
    d.item("a disciplina filtrada, se filtraste alguma;")
    d.item("quantos resultados apareceram;")
    d.item("que documento abriste e em que posição da lista estava.")
    d.nota(
        "O texto das tuas pesquisas é conteúdo teu, e fica guardado. O rótulo não "
        "tem o teu nome, mas existe uma lista que liga rótulos a pessoas \u2014 e por "
        "isso a lei trata este registo como dados pessoais. Não escrevas na caixa "
        "de busca nada que não quisesses ver registado."
    )

    d.titulo_seccao("3. O que não fica registado")
    d.item(
        "O teu endereço IP não é guardado. É usado durante o pedido para travar "
        "excessos e desaparece a seguir; nunca chega a ser escrito em disco."
    )
    d.item("Não há cookies de publicidade, de análise, nem de terceiros.")
    d.item("Não há recolha de dados do dispositivo, do navegador nem do ecrã.")
    d.item(
        "Não há partilha com nenhuma empresa. O Madalena não chama serviço "
        "externo nenhum \u2014 nem sequer para ir buscar tipos de letra."
    )

    d.titulo_seccao("4. Para que serve este registo")
    d.paragrafo(
        "Para uma coisa só: saber se o motor de busca responde bem. As pesquisas "
        "que não devolvem nada mostram o que falta indexar; as que devolvem o "
        "documento certo em primeiro lugar mostram que a ordenação funciona. Sem "
        "este registo, o projeto seria afinado a adivinhar."
    )
    d.paragrafo(
        "O registo não é usado para avaliar ninguém, não é mostrado a professores "
        "e não entra em nota nenhuma."
    )

    d.titulo_seccao("5. Durante quanto tempo")
    d.paragrafo(
        "Os registos são apagados automaticamente ao fim de 90 dias. A limpeza "
        "corre sempre que o servidor arranca. Sobram apenas contagens agregadas "
        "\u2014 quantas buscas houve num dia, que consultas foram mais frequentes "
        "\u2014 que já não permitem chegar a ninguém."
    )

    d.titulo_seccao("6. Cookies")
    d.paragrafo("O Madalena usa um cookie, e mais nenhum:")
    d.item(
        "madalena \u2014 guarda que entraste, para não teres de escrever o código em "
        "cada página. Contém o teu rótulo, a hora de entrada e uma assinatura que "
        "impede que seja falsificado. Dura 30 dias. Não pode ser lido pelo "
        "JavaScript da página nem usado por outros sites."
    )
    d.paragrafo(
        "Este cookie é estritamente necessário para o serviço que pediste ao "
        "entrar com o código. Por isso não há janela a pedir autorização: a lei "
        "dispensa consentimento exactamente neste caso. Se algum dia houver um "
        "cookie que não seja necessário, passa a haver janela."
    )
    d.paragrafo(
        "O navegador guarda ainda duas preferências tuas \u2014 o tema claro ou "
        "escuro e o som ligado ou desligado. Ficam no teu dispositivo e nunca são "
        "enviadas para o servidor."
    )

    d.titulo_seccao("7. Com quem é partilhado, e onde vive")
    d.paragrafo(
        "Com ninguém. O índice e os registos vivem numa só máquina, em Portugal. "
        "Não há nuvem, não há alojamento externo, não há transferências para fora "
        "da União Europeia."
    )
    d.paragrafo(
        "O acesso de fora da escola passa por um túnel cifrado da Cloudflare, que "
        "encaminha o tráfego. Como qualquer intermediário de rede, a Cloudflare vê "
        "que houve ligações; o conteúdo das tuas pesquisas não lhe é entregue nem "
        "guardado por ela."
    )

    d.titulo_seccao("8. Os teus direitos")
    d.paragrafo("A qualquer momento, e sem teres de justificar, podes pedir para:")
    d.item("ver tudo o que está registado com o teu rótulo;")
    d.item("apagar o teu histórico, no todo ou em parte;")
    d.item("sair do piloto \u2014 o rótulo é anulado e o registo apagado;")
    d.item("opores-te ao registo e continuares a usar o motor.")
    d.paragrafo(
        f"Basta pedir a {CONTACTO}. A resposta chega em menos de 30 dias, e "
        "normalmente no próprio dia."
    )

    d.titulo_seccao("9. Se és menor de idade")
    d.paragrafo(
        "Este piloto é para alunos, e a maioria é menor. A participação precisa da "
        "autorização do teu encarregado de educação, dada antes de te ser entregue "
        "o código, e pode ser retirada a qualquer momento sem qualquer "
        "consequência."
    )

    d.titulo_seccao("10. Se achares que alguma coisa está mal")
    d.paragrafo(
        "Fala primeiro comigo ou com um professor \u2014 resolve-se mais depressa. "
        "Tens também o direito de apresentar reclamação à Comissão Nacional de "
        "Proteção de Dados (www.cnpd.pt)."
    )

    d.separador()
    d.paragrafo(
        "Este é um projeto escolar em fase de teste. Se alguma coisa neste "
        "documento não corresponder ao que o sistema faz, o erro é do documento e "
        "deve ser comunicado.",
        tamanho=9, cinzento=0.45,
    )
    return d


def pedido_remocao() -> Documento:
    d = Documento(
        "Pedido de remoção do índice",
        "Dados pessoais, documentos internos e direitos de autor",
    )

    d.paragrafo(
        "O Madalena é um catálogo: encontra documentos, mas não os aloja. Se "
        "pedires a remoção, o documento deixa de aparecer nas pesquisas \u2014 mas "
        "continua onde está, no Moodle ou no site da escola. Para o tirar de lá é "
        "preciso falar com a escola, e nós ajudamos a fazer esse pedido."
    )
    d.nota(
        "Pedidos sobre dados pessoais \u2014 teus ou de outra pessoa \u2014 são tratados "
        "com prioridade: o documento é retirado do índice enquanto se analisa o "
        "pedido, e não depois. É mais barato retirar por engano do que deixar "
        "exposto."
    )

    d.titulo_seccao(f"Preenche e envia para {CONTACTO}")

    d.campo(
        "Documento",
        "Título ou endereço do documento no Madalena. Se forem vários, lista-os "
        "todos.",
    )
    d.campo(
        "Motivo",
        "Dados pessoais meus / Dados pessoais de outra pessoa / Documento interno "
        "que não devia estar acessível / Direitos de autor / Outro",
    )
    d.campo(
        "Qual é o problema",
        "Que informação concreta está lá e não devia, e em que página do "
        "documento.",
    )
    d.campo(
        "Quem és",
        "Aluno / Encarregado de educação / Professor ou funcionário / Outro",
    )
    d.campo(
        "Contacto",
        "Endereço de correio para a resposta. Usado só para isso e apagado no fim.",
    )
    d.campo(
        "Relação com a pessoa",
        "Só se o pedido for sobre dados de outra pessoa.",
        obrigatorio=False,
    )
    d.campo(
        "Declaração",
        "Escreve: confirmo que o que declarei é verdade, tanto quanto sei.",
    )

    d.titulo_seccao("O que acontece a seguir")
    d.item("Recebes confirmação com um número de pedido.")
    d.item(
        "Se o motivo forem dados pessoais, o documento sai do índice em 24 horas, "
        "antes de qualquer análise."
    )
    d.item("A análise demora até 5 dias úteis.")
    d.item(
        "A decisão é comunicada por escrito e fundamentada, e pode ser contestada."
    )
    d.item(
        "Se o problema estiver na origem e não no índice, o pedido é encaminhado "
        "para a escola e acompanhado."
    )

    d.titulo_seccao("Direitos de autor")
    d.paragrafo(
        "Material escolar contém, com frequência, páginas de manuais e fichas de "
        "editoras. O artigo 75.º/2 do Código do Direito de Autor admite "
        "utilizações para fins de ensino, portanto nem tudo o que está indexado é "
        "uma infração. Ainda assim, se és titular de direitos sobre uma obra e a "
        "encontras aqui, usa este mesmo formulário indicando a obra, a editora e o "
        "ISBN, e identifica-te \u2014 a lei exige identificação real para este tipo "
        "de pedido."
    )

    d.separador()
    d.paragrafo(
        "Não há formulário em linha para isto de propósito: um pedido de remoção "
        "deve deixar rasto escrito de quem pediu e do que foi decidido.",
        tamanho=9, cinzento=0.45,
    )
    return d


ECRAS = RAIZ / "assets" / "manual"


def manual_utilizador() -> Documento:
    d = Documento(
        "Manual do utilizador",
        "Madalena Search \u2014 como procurar material da escola",
    )

    d.paragrafo(
        "O Madalena procura dentro de tudo o que a escola publica: horários, "
        "fichas, planificações, regulamentos e as páginas do site. Procura no "
        "texto dos ficheiros e não só no nome deles \u2014 por isso encontra uma "
        "página no meio de um PDF de duzentas."
    )
    d.nota(
        "O Madalena é um catálogo: encontra os documentos e leva-te até eles, mas "
        "quem os guarda continua a ser a escola. Um documento que não esteja no "
        "Moodle nem no site não existe aqui."
    )

    # ---------------------------------------------------------------- entrar
    d.titulo_seccao("1. Entrar")
    d.paragrafo(
        "O acesso é por código. Cada participante tem o seu, e o código é pessoal "
        "\u2014 não o partilhes, porque tudo o que for pesquisado com ele fica "
        "associado a ti."
    )
    d.imagem(
        ECRAS / "entrada.png",
        "A porta de entrada. Escreve o código e carrega em Entrar. Ficas dentro "
        "durante 30 dias, sem ter de repetir.",
    )
    d.paragrafo(
        "Os dois botões ao lado de \u201cacesso restrito\u201d ligam e desligam o "
        "som dos cliques e trocam entre tema claro e escuro. A escolha fica "
        "guardada no teu dispositivo."
    )

    # --------------------------------------------------------------- procurar
    d.titulo_seccao("2. Procurar")
    d.imagem(
        ECRAS / "inicial.png",
        "A página inicial. Escreve na caixa e carrega Enter. As três palavras "
        "sublinhadas por baixo são atalhos para as buscas mais feitas pela turma.",
    )

    d.paragrafo("Enquanto escreves, aparecem sugestões:")
    d.imagem(
        ECRAS / "sugestoes.png",
        "Sobe e desce com as setas, escolhe com Enter, fecha com Esc. As que "
        "dizem \u201cjá pesquisou\u201d vieram do que a turma já procurou; as "
        "outras são palavras que existem mesmo nos documentos.",
        largura_max=430,
    )

    d.titulo_seccao("3. Ler os resultados")
    d.imagem(
        ECRAS / "resultados.png",
        "Cada resultado tem três linhas: o tipo de documento e a disciplina, o "
        "título, e um trecho com as tuas palavras a negrito.",
    )
    d.item(
        "A seta ao lado do título abre o documento numa janela nova, no Moodle "
        "ou no site."
    )
    d.item(
        "\u201ce mais 2 páginas neste documento\u201d quer dizer que as tuas "
        "palavras aparecem noutras páginas do mesmo ficheiro. Aparece uma vez só, "
        "pela melhor página, para não encher a lista com o mesmo PDF."
    )
    d.item(
        "Os separadores por cima da lista \u2014 Tudo, Regulamentos, Fichas e "
        "materiais, Páginas do site \u2014 dividem o que encontraste por tipo. O "
        "número ao lado diz quantos são."
    )
    d.item(
        "A coluna da esquerda limita a busca a uma disciplina. Muda e a lista "
        "refaz-se logo."
    )
    d.paragrafo(
        "No computador, se parares o rato em cima de um resultado durante um "
        "segundo, abre-se um painel à direita com o início do documento \u2014 dá "
        "para confirmar se é o que procuras sem o abrir. No telemóvel esse painel "
        "não cabe, e em vez dele há um botão \u201cprever\u201d por baixo de cada "
        "resultado."
    )

    d.imagem(
        ECRAS / "paginacao.png",
        "São dez resultados por página. A barra em baixo leva às seguintes e diz "
        "onde estás.",
    )

    # ------------------------------------------------------ escrever melhor
    d.titulo_seccao("4. Escrever melhor a pergunta")
    d.paragrafo(
        "O motor faz algum trabalho por ti. Vale a pena saber qual, porque muda "
        "a maneira de perguntar:"
    )
    d.item(
        "<b>Acentos não contam.</b> \u201cmatematica\u201d e \u201cmatemática\u201d "
        "dão o mesmo. Maiúsculas também não contam."
    )
    d.item(
        "<b>Erros de escrita são corrigidos.</b> Se escreveres "
        "\u201cregulamnto\u201d, o Madalena procura por \u201cregulamento\u201d e "
        "avisa-te do que fez."
    )
    d.item(
        "<b>Siglas são expandidas.</b> PAP, FCT, TPC, PSI, RI, PAA, EE e CP "
        "encontram também os documentos que escrevem a expressão por extenso."
    )
    d.item(
        "<b>Dizer o nome da disciplina chega.</b> \u201ccritérios de avaliação de "
        "matemática\u201d filtra sozinho por Matemática \u2014 não é preciso mexer "
        "na coluna da esquerda."
    )
    d.item(
        "<b>\u201cúltimo\u201d e \u201cmais recente\u201d ordenam por data.</b> "
        "\u201cúltimo horário\u201d traz primeiro o mais novo, e não o mais parecido."
    )
    d.item(
        "<b>Perguntas funcionam.</b> \u201cquando começam as aulas\u201d é uma busca "
        "válida; as palavras de pergunta são ignoradas na conta e as outras é que "
        "procuram."
    )
    d.paragrafo(
        "Duas ou três palavras de conteúdo costumam bastar. Frases longas não "
        "ajudam \u2014 quantas mais palavras, mais estreita fica a busca."
    )

    d.titulo_seccao("5. Quando não aparece nada")
    d.imagem(
        ECRAS / "vazio.png",
        "Sem resultados. Não quer dizer que o documento não exista: pode não "
        "estar indexado.",
        largura_max=430,
    )
    d.item("Tira palavras em vez de acrescentar.")
    d.item("Tenta o nome do ficheiro, se o souberes de cor.")
    d.item("Tira o filtro de disciplina \u2014 muita coisa está em \u201cEscola\u201d.")
    d.item(
        "Se mesmo assim não aparecer, avisa: as buscas que falham são a lista do "
        "que falta indexar, e é assim que o Madalena melhora."
    )

    d.titulo_seccao("6. As outras páginas")
    d.imagem(
        ECRAS / "novidades.png",
        "Material novo: o que apareceu no Moodle nos últimos dias.",
        largura_max=430,
    )
    d.imagem(
        ECRAS / "estatisticas.png",
        "Estatísticas: quanto se usou e o que se procurou. Não mostra quem "
        "procurou o quê \u2014 consultas feitas por uma só pessoa são escondidas.",
    )

    d.titulo_seccao("7. No telemóvel")
    d.imagem(
        ECRAS / "telemovel.png",
        "A mesma coisa, numa coluna. O trecho corta-se a duas linhas para caberem "
        "mais resultados no ecrã.",
        largura_max=210,
    )

    d.titulo_seccao("8. O que fica registado")
    d.paragrafo(
        "Fica registado o que escreves na caixa de busca, a data, e o documento "
        "que abres, ligados ao teu rótulo (aluno-01, aluno-02...) e não ao teu "
        "nome. O endereço IP não é guardado, e tudo é apagado ao fim de 90 dias."
    )
    d.paragrafo(
        f"Serve para saber se o motor responde bem. Podes pedir para ver ou "
        f"apagar o teu registo a qualquer momento: {CONTACTO}. A Política de "
        "Privacidade explica isto em detalhe e está na página \u201cOs teus "
        "dados\u201d, ligada do rodapé."
    )

    d.separador()
    d.paragrafo(
        "Projeto escolar em fase de teste. Se alguma coisa não funcionar como "
        "está aqui descrito, o erro pode ser do programa ou do manual \u2014 nos "
        "dois casos vale a pena avisar.",
        tamanho=9, cinzento=0.45,
    )
    return d


def termos_de_uso() -> Documento:
    d = Documento(
        "Termos de uso",
        "Madalena Search \u2014 condi\u00e7\u00f5es de utiliza\u00e7\u00e3o do piloto",
    )

    d.paragrafo(
        "Ao entrares com o teu código, aceitas estas condições. São curtas de "
        "propósito."
    )

    d.titulo_seccao("1. O que é o Madalena")
    d.paragrafo(
        "Um motor de busca sobre o material que a escola já publica: o site "
        "sefo.pt e o Moodle. É um <b>catálogo</b> \u2014 encontra documentos e "
        "leva-te até eles, mas não os aloja nem os substitui. A fonte continua a "
        "ser a escola."
    )
    d.paragrafo(
        f"É um projeto escolar desenvolvido por {RESPONSAVEL}, em fase de teste "
        "fechado. <b>Não é um serviço oficial da escola</b> e não substitui os "
        "canais oficiais."
    )

    d.titulo_seccao("2. Quem pode usar")
    d.paragrafo(
        "Só participantes convidados, com um código de acesso. O código é "
        "pessoal e intransmissível: tudo o que for pesquisado com ele fica "
        "associado ao teu rótulo. Se o partilhares, respondes pelo que for feito "
        "com ele."
    )
    d.paragrafo(
        "Se és menor de idade, a participação precisa da autorização do teu "
        "encarregado de educação."
    )

    d.titulo_seccao("3. O que podes fazer")
    d.item("Procurar e abrir qualquer documento que apareça nos resultados.")
    d.item("Usar o que encontras para estudar e para os teus trabalhos.")
    d.item("Dizer o que não funciona, o que falta, e o que devia sair do índice.")

    d.titulo_seccao("4. O que não podes fazer")
    d.item("Partilhar o teu código, ou usar o de outra pessoa.")
    d.item(
        "Descarregar o índice de forma automática, ou fazer pedidos em massa. Há "
        "um limite por minuto, e ultrapassá-lo de propósito é motivo para "
        "suspensão."
    )
    d.item(
        "Tentar contornar o acesso por código, ou chegar a documentos que não "
        "aparecem nos teus resultados."
    )
    d.item(
        "Republicar em massa material da escola fora dela. O que está no Moodle "
        "é da escola e dos seus autores; encontrá-lo aqui não muda isso."
    )
    d.paragrafo(
        "O acesso pode ser suspenso sem aviso se alguma destas regras for "
        "quebrada. Não há recurso formal: o piloto tem sete pessoas e resolve-se "
        "a falar."
    )

    d.titulo_seccao("5. O que não é garantido")
    d.item(
        "<b>Disponibilidade.</b> O Madalena corre num computador pessoal e não "
        "num servidor. Pode estar desligado, em manutenção, ou simplesmente fora "
        "durante horas."
    )
    d.item(
        "<b>Completude.</b> Nem tudo o que a escola publica está indexado. Não "
        "encontrar não prova que não existe."
    )
    d.item(
        "<b>Atualidade.</b> Um documento pode ter sido substituído na origem sem "
        "que o índice já tenha dado por isso. <b>Para o que conta \u2014 datas de "
        "testes, horários, prazos \u2014 confirma sempre na fonte.</b>"
    )
    d.paragrafo(
        "O serviço é fornecido como está, sem garantia. Quem o desenvolve não "
        "responde por decisões tomadas com base em informação desatualizada "
        "encontrada aqui."
    )

    d.titulo_seccao("6. Direitos sobre o conteúdo")
    d.paragrafo(
        "Os documentos pertencem aos seus autores e à escola. O Madalena guarda "
        "uma cópia do texto apenas para o poder procurar, e mostra um trecho "
        "curto nos resultados."
    )
    d.paragrafo(
        "O código do próprio motor de busca é de quem o escreveu e está público "
        "em github.com/EduhxH."
    )
    d.paragrafo(
        "Se és titular de direitos sobre alguma obra indexada, ou se encontrares "
        "um documento que não devia estar pesquisável, usa o formulário de "
        "remoção. Pedidos sobre dados pessoais são tratados com prioridade e o "
        "documento sai do índice enquanto se analisa."
    )

    d.titulo_seccao("7. Dados")
    d.paragrafo(
        "O que fica registado, porquê e durante quanto tempo está na Política de "
        "Privacidade, que faz parte destes termos. Em resumo: fica o texto das "
        "tuas pesquisas ligado a um rótulo, não fica o teu IP, e tudo é apagado "
        "ao fim de 90 dias."
    )

    d.titulo_seccao("8. Alterações e lei aplicável")
    d.paragrafo(
        "Estes termos podem mudar. A versão em vigor está sempre na página "
        "\u201cOs teus dados\u201d, com a data. Alterações que restrinjam o que "
        "podes fazer são comunicadas antes de entrarem em vigor."
    )
    d.paragrafo(
        "Aplica-se a lei portuguesa. Antes de qualquer outra coisa, fala comigo "
        "ou com um professor."
    )

    d.separador()
    d.paragrafo(
        f"Dúvidas sobre estes termos: {CONTACTO}.",
        tamanho=9, cinzento=0.45,
    )
    return d


def main() -> None:
    documentos = {
        "manual-utilizador.pdf": manual_utilizador(),
        "politica-privacidade.pdf": politica_privacidade(),
        "termos-de-uso.pdf": termos_de_uso(),
        "pedido-remocao.pdf": pedido_remocao(),
    }
    for nome, documento in documentos.items():
        destino = DESTINO / nome
        documento.guardar(destino)
        tamanho = destino.stat().st_size
        print(f"{nome:28s} {len(documento.paginas)} paginas  {tamanho // 1024} KB")


if __name__ == "__main__":
    main()
