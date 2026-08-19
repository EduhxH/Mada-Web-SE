# Etapa 1 — Arquitetura geral

## A ideia central

Um motor de busca responde: **dado um conjunto de documentos e uma consulta,
quais documentos são relevantes?** Ele faz isso em duas fases separadas no tempo:

1. **Indexação** (antes, sem pressa): lê todos os documentos e constrói
   estruturas de dados otimizadas para consulta.
2. **Consulta** (depois, precisa ser rápida): responde usando as estruturas
   prontas, **sem reler os documentos**.

Analogia: o índice remissivo de um livro. O custo de ler o livro inteiro é pago
uma única vez; depois, cada procura é quase instantânea. Trocamos processamento
antecipado por consultas rápidas.

## Fluxo de dados

```text
URL ou documento local
  → fonte de documentos
  → crawler (quando aplicável)
  → fetcher
  → parser HTML
  → texto limpo
  → tokenizer
  → índice invertido
  → SQLite
  ───────────── fronteira indexação / consulta ─────────────
  → processador de consulta
  → busca
  → ranqueador
  → resultados
```

## Responsabilidade de cada componente

| Componente | Papel | Entrada → Saída |
|---|---|---|
| Crawler | Decide **quais** URLs visitar (fila, regras, robots.txt) | URLs conhecidas → URLs agendadas |
| Fetcher | **Baixa** bytes brutos (HTTP ou disco) | URL/caminho → conteúdo bruto |
| Parser | Extrai texto útil do HTML | HTML → texto limpo |
| Tokenizer | Quebra texto em tokens normalizados | texto → tokens |
| Indexer | Constrói o índice invertido | tokens + doc_id → índice |
| Storage | Persiste índice e metadados (SQLite) | índice em memória → disco |
| Query processor | Interpreta a consulta (mesmas regras de normalização!) | texto do usuário → termos |
| Busca | Encontra candidatos no índice | termos → doc_ids |
| Ranker | **Ordena** candidatos por relevância | doc_ids → doc_ids ordenados |
| Interface | Recebe consulta, exibe resultados | usuário ↔ sistema |

## Exemplo com três documentos

| ID | Conteúdo |
|----|----------|
| 1 | "Python é uma linguagem de programação" |
| 2 | "SQLite é um banco de dados leve" |
| 3 | "Programação em Python usa bibliotecas" |

Índice invertido resultante (parcial):

```text
python      → [1, 3]
programacao → [1, 3]
sqlite      → [2]
```

Consulta `python programação` → normaliza → `python`, `programacao` →
interseção das listas → [1, 3] → ranqueia → resultados. O documento 2 nunca é
tocado durante a consulta.

## Lições importantes

- A consulta deve ser normalizada com as **mesmas regras** da indexação,
  senão "Programação" nunca casa com "programacao".
- O crawler **não decide relevância** (isso é papel do ranker, na consulta).
  Ele apenas descobre e agenda URLs segundo regras explícitas: domínio
  permitido, URLs já visitadas, profundidade, limites de requisição.
- O crawler respeita robots.txt e limites de velocidade; jamais contorna
  autenticação, CAPTCHA ou bloqueios.
- Separar crawler/fetcher e indexer/storage permite testar cada peça
  isoladamente (ex.: crawler sem internet, índice sem banco).
