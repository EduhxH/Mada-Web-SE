from pathlib import Path

from pypdf import PdfReader

from app.models.document import Documento

EXTENSOES_TEXTO = {".txt", ".md"}
EXTENSOES_SUPORTADAS = EXTENSOES_TEXTO | {".pdf"}


def carregar(caminho: str | Path) -> list[Documento]:
    caminho = Path(caminho)
    if caminho.is_dir():
        arquivos = sorted(
            p
            for p in caminho.rglob("*")
            if p.suffix.lower() in EXTENSOES_SUPORTADAS
        )
    else:
        if caminho.suffix.lower() not in EXTENSOES_SUPORTADAS:
            raise ValueError(f"Extensão não suportada: {caminho}")
        arquivos = [caminho]

    documentos: list[Documento] = []
    for arquivo in arquivos:
        if arquivo.suffix.lower() == ".pdf":
            documentos.extend(_carregar_pdf(arquivo, primeiro_id=len(documentos) + 1))
        else:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
            documentos.append(
                Documento(
                    id=len(documentos) + 1,
                    titulo=arquivo.name,
                    texto=texto,
                    origem=str(arquivo),
                )
            )
    return documentos


def _carregar_pdf(arquivo: Path, primeiro_id: int) -> list[Documento]:
    leitor = PdfReader(str(arquivo))
    documentos: list[Documento] = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        texto = pagina.extract_text() or ""
        if not texto.strip():
            continue
        documentos.append(
            Documento(
                id=primeiro_id + len(documentos),
                titulo=f"{arquivo.stem} — página {numero}",
                texto=texto,
                origem=f"{arquivo}#pagina={numero}",
            )
        )
    return documentos
