# Estudo linha a linha — Sessão 5: app/indexing/storage.py (SQL/SQLite)

## Conceitos

- **SQLite**: banco embutido no processo (módulo stdlib `sqlite3`), sem
  servidor, sem senha; o banco é UM arquivo (`data/indice.sqlite3`).
- **SQL declarativo**: descreve O QUE se quer; o query planner decide o COMO.
  DDL (CREATE) define estrutura; DML (INSERT/SELECT/DELETE) mexe nos dados.
- **Persistência vs. RAM**: dicionário é O(1) médio mas volátil e limitado à
  memória; banco é O(log n) mas durável e maior que a RAM.

## Esquema

- `documents(id INTEGER PRIMARY KEY, ...)` — em SQLite, INTEGER PRIMARY KEY é
  apelido do rowid: busca por id é o caminho mais rápido do banco.
- `terms(id ... AUTOINCREMENT, termo TEXT NOT NULL UNIQUE)` — UNIQUE cria uma
  árvore B sobre `termo` → busca O(log v). AUTOINCREMENT nunca reusa id.
- `postings(term_id, doc_id, freq, PRIMARY KEY (term_id, doc_id))` — o índice
  invertido achatado (uma posting por linha). A chave composta ordena as
  linhas por (term_id, doc_id): todas as postings de um termo ficam
  contíguas → leitura sequencial após a descida na árvore.
- `REFERENCES` documenta a chave estrangeira, mas SQLite só a FISCALIZA com
  `PRAGMA foreign_keys = ON` (desligado por padrão histórico).
- Desenho normalizado: a string do termo é gravada 1 vez em `terms`; postings
  carregam só um inteiro.

## Código

- `with conexao:` = transação. Sucesso → COMMIT; exceção → ROLLBACK. É o A
  (atomicidade) do ACID: o índice nunca é visto pela metade.
- DELETE na ordem filhos→pais; política "reindexar substitui tudo".
- `executemany` prepara o INSERT uma vez e reexecuta por tupla.
- `?` = placeholder parametrizado: valor viaja separado do SQL, tratado como
  dado puro. Protege de SQL injection. NUNCA montar SQL com f-string.
- `(termo,)` — vírgula cria tupla de 1 elemento.
- `cursor.lastrowid` — id recém-atribuído pelo AUTOINCREMENT, costura as
  postings ao termo.
- `carregar_postings`: JOIN postings×terms; custo O(log v + p); `dict(linhas)`
  devolve o MESMO formato do índice em memória. Termo ausente → {} (rotina);
  `carregar_documento` de id ausente → KeyError (bug).

## Verdades do exercício

1. Queda de energia no meio de salvar_indice → banco intacto com dados
   antigos (atomicidade via `with`).
2. `?` seguro; f-string permitiria injection tipo
   `' UNION SELECT id, texto FROM documents; --` vazando textos.
   (Nuance: `execute()` roda só 1 statement, então `; DROP` empilhado não
   executa por essa via — mas o UNION dentro do próprio SELECT vaza dados.)
3. Tabela `terms` existe por: (a) economia de espaço (string 1x + inteiro
   leve nas postings); (b) árvore B do UNIQUE fica pequena e rasa.
4. carregar_postings = O(log v) na árvore de terms + O(p) leitura contígua
   das postings. Trocamos O(1) da RAM por durabilidade e escala em disco.

## Descoberta empírica (exercício 5 — dados REAIS do livro)

Top termos por frequência: sistema(448), dados(408), codigo(374),
arquitetura(320), software(315), componentes(311), **c(223)**, componente,
pode, figura, muito, quando, nivel, **1(169)**, uso.

- CORREÇÃO IMPORTANTE: NÃO há stopwords clássicas ("de/a/o/que") no topo —
  porque o tokenizer JÁ as remove antes de indexar. O filtro funciona. O topo
  é dominado por palavras de CONTEÚDO, como se espera de um bom índice.
- Intrusos reais: `c` (223) e `1` (169) — fragmentos de 1 caractere vindos de
  títulos em versalete ("C ONCLUSÃO") e numeração de figuras. Confirma o
  defeito de extração previsto.
- Palavras fracas fora da lista de stopwords: pode, muito, quando — candidatas
  a expansão da lista.
- Ação corretiva natural: filtrar tokens de comprimento < 2 no tokenizer
  (remove `c`, `1` e órfãos do versalete). Exige reindexar para valer.

## Correção aplicada (fecho do ciclo diagnóstico→conserto→medição)

Implementado `COMPRIMENTO_MINIMO = 2` no tokenizer: tokens de 1 caractere são
descartados em toda tokenização. Testes atualizados (28 passando), livro
reindexado. Resultado medido:
- vocabulário: 9238 → 9205 termos únicos (33 fragmentos de 1 char removidos);
- termos de 1 caractere restantes no índice: 0;
- top-15 antes: ...componentes, **c(223)**, componente, ..., **1(169)**, uso;
- top-15 depois: ...componentes, componente, pode, figura, muito, quando,
  nivel, uso, sobre, cada — só palavras de conteúdo, sem órfãos.
Continua não sendo palavra de conteúdo ideal: pode, muito, quando, sobre,
cada — candidatas a futura expansão da lista de stop words.
