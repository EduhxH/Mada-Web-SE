# Estudo linha a linha — Sessão 4: app/indexing/inverted_index.py (Etapa 6)

## Conceitos da etapa

- Índice direto: doc → termos. Índice INVERTIDO: termo → docs que o contêm
  ("python → postings dos documentos 2 e 5").
- Posting list = documentos onde o termo ocorre; nossa posting carrega
  doc_id + frequência (insumo do TF-IDF, coletado numa passada só).
- Representação em memória: dict de dicts —
  `{"python": {1: 1, 3: 1, 4: 4}, "sqlite": {2: 1}}`.

## Pontos do código

- `Counter` (collections): subclasse de dict para contagem; O(m) para contar
  os tokens de um doc; `.items()` itera pares (termo, freq) — sobre termos
  ÚNICOS (u ≤ m), não sobre todos os tokens.
- Retorno `tuple[indice, tamanhos]`: Python empacota múltiplos retornos em
  tupla; quem chama desempacota. `tamanhos[doc.id] = len(tokens)` (len é
  O(1)) será o denominador do TF.
- `indice.setdefault(termo, {})[doc.id] = freq` — termo novo: insere {} e o
  devolve; termo existente: ignora o padrão e devolve a posting atual. Uma
  consulta ao hash em vez de duas, e o caso "termo novo" nunca é esquecido.
  (O {} do argumento é construído mesmo sem uso; `defaultdict(dict)`
  eliminaria isso — custo de constante aceito pela clareza.)
- Tokenização acontece UMA vez por documento, aqui — o custo que a busca
  ingênua pagava a cada consulta.

## Custos

- Tempo O(T), T = total de tokens: cada token participa de nº constante de
  operações O(1) médias (tokenizar, contar, inserir).
- Espaço: uma entrada por par (termo, doc) distinto + vocabulário ≤ O(T).

## Verdades verificadas no exercício

1. setdefault nos dois cenários (primeira vs. décima ocorrência) — descrito
   com precisão.
2. Posting como dict: `postings.get(doc_id)` do ranker em O(1) médio;
   lista de tuplas custaria O(p) por consulta pontual.
3. Laço interno roda u vezes (termos únicos); diferença enorme em textos
   repetitivos, nula quando nenhum termo se repete.
4. Documento vazio: tamanho 0, zero voltas do Counter, ausente de toda
   posting → nunca vira candidato → `freq / tamanhos[doc_id]` nunca divide
   por zero; para candidatos, freq ≥ 1 ⇒ tamanho ≥ 1.
5. Índice manual da fixture: correto para os termos pedidos.
   Correção registrada: "sobre" NÃO está na nossa STOP_WORDS (a lista é
   explícita, não intuição) — Doc 4 tem 7 tokens válidos, não 6, e
   tamanhos[4] = 7. Consequência real: TF de python no Doc 4 é 4/7, não 4/6.
   O teste test_tamanhos_dos_documentos ancora esse tipo de fato.
