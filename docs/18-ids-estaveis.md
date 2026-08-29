# Ids estáveis: reindexar sem partir o histórico

## O problema

Os ids dos documentos eram atribuídos por ordem de leitura:

```python
id = len(documentos) + 1
```

Enquanto o corpus não muda, funciona. Mas os eventos de utilização guardam
`doc_id` — cada clique de um beta tester aponta para um número.

Se em outubro um professor publicar fichas novas e o índice for reconstruído,
os ficheiros mudam de posição na ordem alfabética e **todos os ids a seguir
deslocam-se**. O documento 226 deixa de ser o mesmo. Consequências:

- os cliques registados passam a apontar para documentos errados
- "mais abertos nesta disciplina" mostra coisas ao acaso
- a medição de utilização, que é o objetivo da apresentação, fica corrompida
  em silêncio

## A correção

O id passa a derivar da **origem** do documento, não da ordem:

```python
def id_estavel(origem: str) -> int:
    resumo = hashlib.blake2b(origem.encode("utf-8"), digest_size=6).hexdigest()
    return int(resumo, 16)
```

A origem já é única por documento — inclui o caminho, o ficheiro dentro do
ZIP (`arquivo.zip!interno.pdf`) e a página (`#pagina=12`). O mesmo documento
produz sempre o mesmo id, indexe-se quantas vezes for preciso.

**48 bits** (6 bytes): com milhares de documentos, a probabilidade de colisão
é de cerca de 1 em centenas de milhões. Ainda assim, ids repetidos são
detetados durante a carga e reportados como `documento repetido` — o que
também serve de deduplicação se o mesmo ficheiro aparecer duas vezes.

## Verificado no corpus real

| Cenário | Documentos | Ids mantidos |
|---|---|---|
| Reindexar sem alterações | 1797 → 1797 | **1797/1797** |
| Acrescentar 3 ficheiros novos | 1797 → 1800 | **1797/1797** |

Zero deslocamentos nos dois casos. É exatamente o que vai acontecer a 15 de
setembro e sempre que houver material novo durante o beta.

## Procedimento de atualização

```bash
# apagar o que e de teste (indice, metricas, codigos, material antigo)
rm data/indice.sqlite3 data/uso.sqlite3 data/participantes.json data/segredo.txt
rm -r data/raw/psi9

# descarregar o material novo para data/raw/psi9/<Disciplina>/
python main.py rastrear https://www.sefo.pt --max-paginas 300
python main.py indexar data/raw
python main.py participantes --criar 8
```

Durante o beta, para acrescentar material sem perder métricas, basta colocar
os ficheiros novos e correr `indexar` — os ids antigos ficam onde estavam.

**Atenção ao descarregar:** o browser acrescenta `(1)`, `(2)` quando o nome
já existe. Apagar a pasta antes evita duplicados de conteúdo antigo.
