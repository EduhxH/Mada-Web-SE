# Estudo linha a linha — Sessão 6: query.py + ranker.py

Divisão de trabalho: `query.py` **encontra**, `ranker.py` **ordena**.
Separar permite trocar a fórmula de relevância sem tocar na busca, e testar
o ranking com postings inventadas à mão (`test_ranker.py`).

## query.py

- `set(tokenizar(consulta))` — o `set()` (que a busca ingênua não tinha)
  existe porque aqui **cada termo custa uma ida ao SQLite**. Termo repetido
  sem o conjunto = mesma consulta ao disco duas vezes. Na ingênua, repetir
  custava só um teste `in` em memória.
- `if not termos: return []` — mesma semântica da ingênua, obrigatoriamente:
  se divergirem, o teste do oráculo falha. Duas implementações, um contrato.
- `sorted(..., key=len)` — **a otimização central**. A interseção nunca é
  maior que o menor conjunto, então começar pequeno faz cada passo seguinte
  percorrer poucos elementos. Listas 5/400/900: ~10 comparações começando
  pela de 5; 900 logo de início se começasse pela maior. Resultado idêntico.
- `if not listas[0]` — basta testar a primeira: depois de ordenadas, se
  alguma está vazia é essa. Termo inexistente mata a lógica E.
- `candidatos &= postings.keys()` — `dict.keys()` é uma **vista com
  comportamento de conjunto**: suporta `&` sem copiar nada. `set(keys())`
  construiria um conjunto novo a cada volta.
- Saída antecipada quando a interseção esvazia: poupa as interseções
  restantes E as consultas de tamanhos/total.
- Hidratação final: doc_ids -> Documentos.

## ranker.py

- Laços aninhados: k candidatos x q termos.
- `len(postings)` **é o df** — o número de docs que contêm o termo é o
  tamanho da posting list. A estrutura já sabe; não há nada a calcular.
- `sort(key=lambda par: par[1], reverse=True)` — Timsort, O(k log k),
  estável (empates mantêm a ordem anterior).

## TF-IDF

```
TF  = freq(t, doc) / tamanho(doc)     "este doc fala MUITO disto?"
IDF = log(N / df(t))                  "este termo DISTINGUE alguma coisa?"
```

- A divisão no TF impede que documento longo ganhe por ser longo.
- `df = N` (termo em todo o lado) -> `log(1) = 0` -> contribui zero.
- **Porquê log?** Sem ele, um termo em 1 de 1000 docs valeria 1000x mais que
  um presente em todos — desproporcionado. O log amortece: dez vezes mais
  raro soma `log(10)`, um acréscimo constante, não dez vezes.
- O produto premia o termo **frequente aqui e raro em todo o lado**.

## Diagnósticos do exercício (a corrigir)

1. **IDF recalculado no laço errado**: o IDF não depende de `doc_id`, mas é
   calculado dentro do laço dos candidatos. Com 18 candidatos e 3 termos são
   **54 chamadas a `math.log` onde bastavam 3**. Correção: pré-calcular por
   termo antes do laço.
2. **N+1 queries**: `carregar_documento` dentro da compreensão faz uma
   consulta SQL por resultado. Correção: uma única consulta com `WHERE id IN
   (...)`.
3. **`if freq is None` é código morto hoje**: com lógica E, todo candidato
   está em todas as posting lists. Fica vivo quando existir **OU** — e só
   com OU. (O filtro por disciplina *não* o ativa: filtrar só remove
   candidatos, nunca acrescenta candidatos sem os termos.)

## Onde entra o filtro

```
candidatos &= postings.keys()        <- busca (existe)
candidatos &= docs_da_disciplina     <- filtro (a acrescentar)
tamanhos = storage.carregar...       <- ranking (existe)
```

Mais uma interseção de conjuntos. A ACL por turma entra na mesma linha.

## Correções aplicadas (2026-08-25)

### 1. IDF pré-calculado
`idf_por_termo` é construído **antes** do laço dos candidatos. Com 18
candidatos e 3 termos: 3 logaritmos em vez de 54. A classe Big O não muda
(continua O(k×q)), mas sai uma operação cara do laço mais quente — otimização
de constante, exatamente o que a Etapa 3 diz que Big O não mostra mas o
relógio sente.

### 2. N+1 resolvido com `IN`
`storage.carregar_documentos(conexao, ids)` faz **uma** consulta por lote:

```python
marcadores = ",".join("?" * len(lote))
conexao.execute(f"... WHERE id IN ({marcadores})", lote)
```

**Ponto de segurança:** este é o único sítio do projeto onde se constrói SQL
por formatação de string — e é seguro porque o que se interpola é a
**contagem** de marcadores (`?,?,?`), nunca os valores. Os dados continuam a
viajar pelo caminho parametrizado. Interpolar os ids diretamente reabriria a
porta do injection da Sessão 5.

Dois detalhes:
- **Lotes de 500**: o SQLite tem limite de parâmetros por instrução.
- **`IN` não garante ordem**: por isso a função devolve um `dict` e o
  `query.py` reconstrói a ordem a partir do ranking.

### Medição na coleção real (787 documentos)

| Consulta | Resultados | Consultas SQL | Tempo (quente) |
|---|---|---|---|
| "trabalho" | 167 | **4** (eram ~170) | 7–14 ms |
| "base de dados" | 18 | 5 | ~6 ms |
| "ficha" | 24 | 4 | ~6 ms |

Primeira consulta após abrir a ligação: ~880 ms (arranque a frio — o SQLite
carrega páginas do disco e valida o esquema). A partir daí, milissegundos.
Lição: **medir a segunda execução**, não a primeira.

## O defeito que a medição revelou

`buscar()` hidrata **todos** os resultados, mas a interface só mostra 20.
Para "trabalho" isso são **236 KB de texto lidos do disco para mostrar 20
documentos**. O ranking precisa de todos os candidatos (senão o topo estaria
errado), mas o *texto completo* só é preciso para os que aparecem.

Correção futura: separar "ranquear todos" de "hidratar os visíveis" —
o que naturalmente leva a **paginação**.
