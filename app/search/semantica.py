"""Busca semantica: encontra pelo significado, nao pelas palavras.

Existe por uma falha medida: "quando comecam as aulas" nao chega ao
calendario, que diz "INICIO DAS AULAS". Zero palavras em comum, e nenhuma
regra de plural ou de grafia atravessa essa distancia.

Tres decisoes desta implementacao vieram de medicao, nao de gosto:

1. MINUSCULAS antes de embeber. O modelo trata maiusculas como outra coisa:
   "quando comecam as aulas" contra "INICIO DAS AULAS" da 0.37, contra
   "inicio das aulas" da 0.93. O corpus da escola esta cheio de titulos em
   caixa alta, e sem isto metade do ganho evapora-se.

2. FRAGMENTAR. O modelo le 128 tokens e ignora o resto - medido, apesar de a
   ficha dizer 512. 70% dos documentos passam disso. Pior: a diluicao comeca
   antes do corte, porque o vetor e a media do texto todo; numa pagina com 40
   datas, cada uma vale 1/40. O documento continua a ser a unidade de
   resultado, mas a unidade de embedding passa a ser o fragmento.

3. FORCA BRUTA. Sao ~9 mil vetores de 384 dimensoes: 13 MB, um produto de
   matrizes que o numpy faz em milissegundos. Uma base de dados vetorial aqui
   seria dependencia sem retorno.
"""

import sqlite3
from dataclasses import dataclass

import numpy as np

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSOES = 384

# Medido: o modelo corta aos 128 tokens, e a diluicao ja e forte aos 50
# vocabulos. 300 caracteres (~85 tokens em portugues) fica com folga dentro
# da janela e mantem o fragmento com um assunto so.
TAMANHO_FRAGMENTO = 300
# Sobreposicao para um facto nao morrer partido entre dois fragmentos.
SOBREPOSICAO = 60
# Abaixo disto o fragmento e um restinho de pagina sem conteudo util.
FRAGMENTO_MINIMO = 40

_modelo = None


def carregar_modelo():
    """Carrega uma vez e reutiliza: instanciar custa segundos."""
    global _modelo
    if _modelo is None:
        from fastembed import TextEmbedding

        _modelo = TextEmbedding(MODELO)
    return _modelo


def fragmentar(texto: str) -> list[str]:
    """Parte o texto em pedacos que cabem na janela do modelo.

    Corta em espaco para nao partir palavras a meio, e so aceita o corte se
    ele nao andar demasiado para tras.
    """
    limpo = " ".join((texto or "").split())
    if len(limpo) <= TAMANHO_FRAGMENTO:
        return [limpo] if len(limpo) >= FRAGMENTO_MINIMO else []

    fragmentos = []
    inicio = 0
    while inicio < len(limpo):
        fim = min(inicio + TAMANHO_FRAGMENTO, len(limpo))
        if fim < len(limpo):
            espaco = limpo.rfind(" ", inicio + TAMANHO_FRAGMENTO // 2, fim)
            if espaco != -1:
                fim = espaco
        pedaco = limpo[inicio:fim].strip()
        if len(pedaco) >= FRAGMENTO_MINIMO:
            fragmentos.append(pedaco)
        if fim >= len(limpo):
            break
        # O recuo da sobreposicao cai onde calha, e comecar a meio de uma
        # palavra parte o facto em dois: "INICIO DAS AULAS" virava
        # "...DAS AUL" + "AS PARA...", que e o oposto do que se quer.
        recuo = max(fim - SOBREPOSICAO, inicio + 1)
        espaco = limpo.find(" ", recuo)
        inicio = espaco + 1 if 0 <= espaco < fim else recuo
    return fragmentos


def preparar(texto: str, titulo: str = "") -> str:
    """Texto como vai para o modelo.

    Minusculas pela razao medida no cabecalho. O titulo entra a frente de
    cada fragmento porque diz de que documento se trata: sem ele, um
    fragmento no meio de uma sebenta perde o contexto todo.
    """
    junto = f"{titulo}. {texto}" if titulo else texto
    return junto.lower()


def criar_esquema(conexao: sqlite3.Connection) -> None:
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS fragmentos (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id  INTEGER NOT NULL REFERENCES documents(id),
            ordem   INTEGER NOT NULL,
            texto   TEXT NOT NULL,
            vetor   BLOB NOT NULL
        )
        """
    )
    conexao.execute(
        "CREATE INDEX IF NOT EXISTS idx_fragmentos_doc ON fragmentos(doc_id)"
    )
    conexao.commit()


def embeber(textos: list[str]) -> np.ndarray:
    """Vetores normalizados, para o cosseno ser um produto interno."""
    modelo = carregar_modelo()
    vetores = np.array(list(modelo.embed(textos)), dtype=np.float32)
    normas = np.linalg.norm(vetores, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return vetores / normas


def guardar(conexao, doc_id: int, fragmentos: list[str], vetores: np.ndarray) -> None:
    conexao.executemany(
        "INSERT INTO fragmentos (doc_id, ordem, texto, vetor) VALUES (?,?,?,?)",
        [
            (doc_id, ordem, texto, vetor.astype(np.float32).tobytes())
            for ordem, (texto, vetor) in enumerate(zip(fragmentos, vetores))
        ],
    )


@dataclass
class Matriz:
    """Todos os vetores em memoria, prontos para um produto de matrizes."""

    vetores: np.ndarray
    docs: np.ndarray

    def __len__(self) -> int:
        return len(self.docs)


def carregar_matriz(conexao) -> Matriz | None:
    linhas = conexao.execute(
        "SELECT doc_id, vetor FROM fragmentos ORDER BY id"
    ).fetchall()
    if not linhas:
        return None
    vetores = np.frombuffer(
        b"".join(vetor for _, vetor in linhas), dtype=np.float32
    ).reshape(len(linhas), DIMENSOES)
    docs = np.array([doc_id for doc_id, _ in linhas], dtype=np.int64)
    return Matriz(vetores, docs)


def procurar(matriz: Matriz, pergunta: str, limite: int = 40) -> dict[int, float]:
    """Documentos mais proximos da pergunta, com a melhor pontuacao de cada.

    Um documento vale o seu melhor fragmento e nao a media deles: uma pagina
    com quarenta datas responde pela data certa, nao pelo conjunto.
    """
    if matriz is None or not len(matriz):
        return {}

    consulta = embeber([pergunta.lower()])[0]
    semelhancas = matriz.vetores @ consulta

    quantos = min(limite * 4, len(semelhancas))
    melhores = np.argpartition(-semelhancas, quantos - 1)[:quantos]

    por_documento: dict[int, float] = {}
    for indice in melhores:
        doc_id = int(matriz.docs[indice])
        valor = float(semelhancas[indice])
        if valor > por_documento.get(doc_id, -1.0):
            por_documento[doc_id] = valor
    return dict(
        sorted(por_documento.items(), key=lambda par: -par[1])[:limite]
    )
