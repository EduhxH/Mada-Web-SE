# Etapa 4+ — O código implementado, módulo a módulo

Este guia mapeia o que foi implementado, as decisões tomadas e onde cada
conceito das etapas anteriores aparece no código. É o roteiro para o estudo
linha a linha.

## O caminho de um documento (indexação)

```text
data/raw/arquitetura-limpa.pdf
  → app/crawler/local_source.py   carregar(): cada página vira um Documento
  → app/indexing/tokenizer.py     tokenizar(): minúsculas, sem acentos,
                                  [a-z0-9]+, stop words fora
  → app/indexing/inverted_index.py construir_indice(): termo → {doc_id: freq}
  → app/indexing/storage.py       salvar_indice(): tabelas documents,
                                  terms, postings no SQLite
```

## O caminho de uma consulta

```text
"inversao de dependencia"
  → app/search/query.py     tokenizar com as MESMAS regras
  → storage.carregar_postings() por termo (JOIN terms→postings, O(log n))
  → interseção dos doc_ids, começando pela menor posting list
  → app/search/ranker.py    pontuar(): TF-IDF + ordenação decrescente
  → main.py                 exibe título, pontuação e trecho
```

## Decisões de projeto (e por quê)

1. **Uma página de PDF = um Documento.** O resultado aponta a página exata —
   num livro de 480 páginas, "está no arquivo" seria inútil.
2. **`Documento` é um dataclass `frozen`** (imutável, como tupla): nenhum
   componente altera um documento por acidente; registros são passados entre
   módulos com segurança.
3. **Stop words numa lista explícita e pequena** (tokenizer.py). Sem elas, a
   busca E por "inversao de dependencia" exigiria "de" — presente em toda
   página, engordando postings sem informação. A lista é auditável e há um
   teste garantindo que ela está normalizada como os tokens.
4. **Índice em memória = dict termo → {doc_id: freq}.** O dict interno é a
   posting list com frequências já contadas (uma passada só, `Counter`).
5. **SQLite com três tabelas** (documents, terms, postings) — a forma
   relacional do dicionário. `terms.termo UNIQUE` cria a árvore B que dá a
   busca O(log n). Gravação dentro de transação: ou tudo, ou nada.
6. **Interseção começa pela menor posting list**: o conjunto de candidatos
   só encolhe, então começar pequeno barateia tudo que vem depois.
7. **TF-IDF**: TF = freq/tamanho do doc (docs longos não vencem só por
   tamanho); IDF = log(N/df) (termo onipresente vale zero). Testes cobrem
   as três propriedades.
8. **A busca ingênua não foi apagada** — é baseline e oráculo: o teste de
   integração exige que o índice retorne exatamente os mesmos documentos.

## Números medidos (coleção real: 480 páginas)

| Operação | Tempo | Observação |
|---|---|---|
| Indexação completa | ~40 s | paga UMA vez (dominada pela extração do PDF) |
| Consulta indexada | ~2–4 ms | independe de reler documentos |
| Consulta ingênua | ~130 ms | renormaliza as 480 páginas a cada consulta |
| Aceleração | ~54× | e cresce com o tamanho da coleção |

## Limitações conhecidas (honestas, para estudo futuro)

- A extração do PDF quebra títulos em versalete: "INVERSÃO" sai como
  "I NVERSÃO" (tokens "i" + "nversao"). O corpo do texto está normal, então
  a busca funciona; melhorar o parser é exercício futuro.
- Consulta é só E (AND). OU, frases exatas e stemming vêm depois.
- `carregar_tamanhos()` lê os tamanhos de todos os docs a cada consulta —
  irrelevante com 480 docs, otimizável com milhões.
- Sem crawler web ainda: a fonte é local. HTML/BeautifulSoup e requests
  entram na etapa do crawler.

## Roteiro sugerido para o estudo linha a linha

1. `app/models/document.py` — dataclasses, imutabilidade
2. `app/indexing/tokenizer.py` — Unicode, regex, frozenset
3. `app/search/naive.py` — o algoritmo O(n×m) da Etapa 4
4. `app/indexing/inverted_index.py` — Counter, setdefault, O(T)
5. `app/indexing/storage.py` — SQL, esquema, transações, árvore B
6. `app/search/query.py` + `ranker.py` — interseção, TF-IDF, ordenação
7. `main.py` — argparse, formatação, trecho de contexto
8. `tests/` — fixtures, oráculo, casos de borda
