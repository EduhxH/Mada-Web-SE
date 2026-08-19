# Etapa 2 — Estruturas de dados no motor de busca

Estrutura de dados = organizar informação para tornar **certas operações
baratas**, aceitando que outras fiquem caras. Cada componente do motor faz uma
pergunta diferente e, por isso, usa uma estrutura diferente.

## Resumo por estrutura

| Estrutura | Papel no motor | Operação-chave | Custo |
|---|---|---|---|
| Lista | Posting list (`python → [1, 3]`); resultados ordenados do ranker | acesso por índice / append | O(1) |
| | | procurar valor (`x in lista`) | **O(n)** |
| Conjunto | URLs já visitadas (crawler); stop words | pertencimento (`x in s`) | O(1) médio |
| | Busca booleana E = interseção | interseção | O(min(n, m)) |
| Dicionário | **O índice invertido em memória**: termo → postings; doc_id → metadados | busca por chave | O(1) médio |
| Fila (FIFO) | Fronteira do crawler (URLs pendentes) | enfileirar / desenfileirar | O(1) |
| Grafo | A própria web: páginas = nós, links = arestas; crawling = travessia | travessia (BFS/DFS) | O(V + E) |
| Tupla | Registro imutável: posting `(doc_id, freq)`, doc `(id, url, titulo)` | acesso por posição | O(1) |
| Tabela relacional | Índice persistido no SQLite (documents, terms, postings) | busca com índice (árvore B) | O(log n) |
| | | varredura sem índice | O(n) |

## Pontos que valem ouro

- **Lista falha em pertencimento** (O(n)); conjunto resolve (O(1) médio via
  hashing). Por isso URLs visitadas ficam num conjunto, nunca numa lista:
  checar 50 links contra 1.000.000 de URLs custa ~50 operações com conjunto
  e até 50.000.000 de comparações com lista.
- **Fila ⇒ busca em largura (BFS)**: explora camada por camada a partir da
  semente, casando com o limite de profundidade. Uma pilha (LIFO ⇒ DFS)
  mergulharia fundo num único site antes de ver o resto.
- Em Python, `list` é **array dinâmico**, não lista ligada; `lista.pop(0)`
  custa O(n). Para fila de verdade, usa-se `collections.deque`.
- O índice invertido em memória = **dicionário** (termo → ...) + **listas**
  (postings) + **tuplas** (`(doc_id, freq)`).
- Tabela relacional é a **versão persistente** das estruturas em memória:
  troca O(1) médio do hash por O(log n) da árvore B, ganhando durabilidade,
  integridade e coleções maiores que a RAM.
- O dicionário achar postings em O(1) **não** torna a consulta inteira O(1):
  ainda há listas para combinar e ranquear (tema da Etapa 3).

## O mapa mental

| Pergunta frequente | Estrutura |
|---|---|
| Quais docs contêm este termo? | Dicionário |
| Já visitei esta URL? | Conjunto |
| Qual a próxima URL a visitar? | Fila |
| Em que ordem mostro resultados? | Lista |
| Como as páginas se conectam? | Grafo |
| Como agrupo dados de um doc? | Tupla |
| Como sobrevive ao desligamento? | Tabela relacional |
