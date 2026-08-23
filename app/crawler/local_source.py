import io
import logging
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import docx
from pptx import Presentation
from pypdf import PdfReader

from app.indexing.tokenizer import remover_acentos
from app.models.document import Documento

logging.getLogger("pypdf").setLevel(logging.ERROR)

EXTENSOES_TEXTO = {".txt", ".md", ".cs"}
EXTENSOES_SUPORTADAS = EXTENSOES_TEXTO | {".pdf", ".docx", ".pptx"}

PASTAS_IGNORADAS = ("bin/", "obj/", ".vs/", "packages/", "__pycache__/")

PADROES_PRIVADOS = ("notas", "pauta", "classifica")

MOTIVO_PRIVADO = "possivel dado pessoal"
MOTIVO_FORMATO = "formato nao suportado"
MOTIVO_BUILD = "artefacto de build"
MOTIVO_SEM_TEXTO = "sem texto extraivel"
MOTIVO_CORROMPIDO = "ficheiro ilegivel"
MOTIVO_ZIP_ANINHADO = "zip dentro de zip"


@dataclass
class Relatorio:
    por_disciplina: Counter = field(default_factory=Counter)
    por_formato: Counter = field(default_factory=Counter)
    ignorados: list[tuple[str, str]] = field(default_factory=list)

    def ignorar(self, nome: str, motivo: str) -> None:
        self.ignorados.append((nome, motivo))

    def motivos(self) -> Counter:
        return Counter(motivo for _, motivo in self.ignorados)

    def por_motivo(self, motivo: str) -> list[str]:
        return [nome for nome, m in self.ignorados if m == motivo]


def carregar(caminho: str | Path) -> tuple[list[Documento], Relatorio]:
    raiz = Path(caminho)
    relatorio = Relatorio()
    documentos: list[Documento] = []

    if raiz.is_dir():
        arquivos = sorted(p for p in raiz.rglob("*") if p.is_file())
    else:
        arquivos = [raiz]

    for arquivo in arquivos:
        _processar(
            nome=arquivo.name,
            dados=arquivo.read_bytes(),
            origem=str(arquivo),
            disciplina=_disciplina(raiz, arquivo),
            documentos=documentos,
            relatorio=relatorio,
        )

    return documentos, relatorio


def _disciplina(raiz: Path, arquivo: Path) -> str:
    if not raiz.is_dir():
        return raiz.parent.name
    relativo = arquivo.relative_to(raiz)
    return relativo.parts[0] if len(relativo.parts) > 1 else raiz.name


def _e_privado(nome: str) -> bool:
    normalizado = remover_acentos(nome.lower())
    return any(padrao in normalizado for padrao in PADROES_PRIVADOS)


def _e_artefacto(caminho_interno: str) -> bool:
    normalizado = caminho_interno.replace("\\", "/").lower()
    return any(pasta in normalizado for pasta in PASTAS_IGNORADAS)


def _processar(
    nome: str,
    dados: bytes,
    origem: str,
    disciplina: str,
    documentos: list[Documento],
    relatorio: Relatorio,
    dentro_de_zip: bool = False,
) -> None:
    extensao = Path(nome).suffix.lower()

    if _e_privado(nome):
        relatorio.ignorar(origem, MOTIVO_PRIVADO)
        return

    if extensao == ".zip":
        if dentro_de_zip:
            relatorio.ignorar(origem, MOTIVO_ZIP_ANINHADO)
            return
        _processar_zip(dados, origem, disciplina, documentos, relatorio)
        return

    if extensao not in EXTENSOES_SUPORTADAS:
        relatorio.ignorar(origem, MOTIVO_FORMATO)
        return

    try:
        unidades = _extrair(extensao, dados)
    except Exception:
        relatorio.ignorar(origem, MOTIVO_CORROMPIDO)
        return

    if not unidades:
        relatorio.ignorar(origem, MOTIVO_SEM_TEXTO)
        return

    base = Path(nome).stem
    for texto, sufixo_titulo, sufixo_origem in unidades:
        documentos.append(
            Documento(
                id=len(documentos) + 1,
                titulo=base + sufixo_titulo,
                texto=texto,
                origem=origem + sufixo_origem,
                disciplina=disciplina,
            )
        )
    relatorio.por_disciplina[disciplina] += len(unidades)
    relatorio.por_formato[extensao] += 1


def _processar_zip(
    dados: bytes,
    origem: str,
    disciplina: str,
    documentos: list[Documento],
    relatorio: Relatorio,
) -> None:
    try:
        arquivo_zip = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        relatorio.ignorar(origem, MOTIVO_CORROMPIDO)
        return

    with arquivo_zip:
        for entrada in arquivo_zip.infolist():
            if entrada.is_dir():
                continue
            interno = entrada.filename
            rotulo = f"{origem}!{interno}"
            if _e_artefacto(interno):
                relatorio.ignorar(rotulo, MOTIVO_BUILD)
                continue
            try:
                conteudo = arquivo_zip.read(entrada)
            except Exception:
                relatorio.ignorar(rotulo, MOTIVO_CORROMPIDO)
                continue
            _processar(
                nome=Path(interno).name,
                dados=conteudo,
                origem=rotulo,
                disciplina=disciplina,
                documentos=documentos,
                relatorio=relatorio,
                dentro_de_zip=True,
            )


def _extrair(extensao: str, dados: bytes) -> list[tuple[str, str, str]]:
    if extensao == ".pdf":
        return _unidades_pdf(dados)
    if extensao == ".pptx":
        return _unidades_pptx(dados)
    if extensao == ".docx":
        return _unidades_docx(dados)
    return _unidades_texto(dados)


def _unidades_pdf(dados: bytes) -> list[tuple[str, str, str]]:
    leitor = PdfReader(io.BytesIO(dados))
    unidades = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        texto = pagina.extract_text() or ""
        if texto.strip():
            unidades.append((texto, f" - pagina {numero}", f"#pagina={numero}"))
    return unidades


def _unidades_pptx(dados: bytes) -> list[tuple[str, str, str]]:
    apresentacao = Presentation(io.BytesIO(dados))
    unidades = []
    for numero, slide in enumerate(apresentacao.slides, start=1):
        partes = [
            forma.text_frame.text
            for forma in slide.shapes
            if forma.has_text_frame
        ]
        texto = "\n".join(partes)
        if texto.strip():
            unidades.append((texto, f" - slide {numero}", f"#slide={numero}"))
    return unidades


def _unidades_docx(dados: bytes) -> list[tuple[str, str, str]]:
    documento = docx.Document(io.BytesIO(dados))
    partes = [paragrafo.text for paragrafo in documento.paragraphs]
    for tabela in documento.tables:
        for linha in tabela.rows:
            partes.append(" ".join(celula.text for celula in linha.cells))
    texto = "\n".join(partes)
    return [(texto, "", "")] if texto.strip() else []


def _unidades_texto(dados: bytes) -> list[tuple[str, str, str]]:
    texto = dados.decode("utf-8", errors="replace")
    return [(texto, "", "")] if texto.strip() else []
