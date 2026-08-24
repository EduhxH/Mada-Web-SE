# Correção ortográfica e abertura de documentos

## Correção ortográfica: distância de edição

`app/search/spelling.py` implementa a **distância de Levenshtein**: o número
mínimo de operações (inserir, remover, substituir uma letra) para transformar
uma palavra noutra.

```
horario  -> horarios    distancia 1  (inserir 's')
matmatica -> matematica  distancia 1  (inserir 'e')
```

### O algoritmo (programação dinâmica)

Constrói-se uma tabela onde cada célula `[i][j]` é a distância entre os
primeiros `i` caracteres de A e os primeiros `j` de B. Cada célula depende de
três vizinhas:

```
atual[j] = min(
    anterior[j] + 1,           # remocao
    atual[j-1] + 1,            # insercao
    anterior[j-1] + custo,     # substituicao (custo 0 se as letras coincidem)
)
```

Guardamos apenas **duas linhas** (a anterior e a atual) em vez da tabela
inteira: o espaço cai de O(m×n) para O(n). Tempo: O(m×n).

Duas podas importantes:
- Se a diferença de comprimentos já excede o limite, devolve-se cedo.
- Se o **mínimo da linha atual** ultrapassa o limite, nenhuma linha seguinte
  pode melhorar — abandona-se (as distâncias só crescem para baixo).

### Como se escolhe a sugestão

Para cada termo da consulta **sem postings** (desconhecido), percorre-se o
vocabulário e escolhe-se o candidato de menor distância; em caso de empate,
o de **maior df** (mais documentos), porque é mais provável ser o que o
utilizador queria.

Regras: só se sugere para termos com 4+ letras (corrigir palavras curtas gera
ruído) e a distância máxima é 2.

O vocabulário só é carregado **quando existe um termo desconhecido** — na
maioria das consultas, custo zero.

### O que isto resolveu

O problema do singular/plural descoberto em `docs/07-relevancia.md`:

```
"horario da turma psi9"  ->  sugere "horarios da turma psi9"
                         ->  topo passa a ser o documento de Horarios
```

Sem stemming, sem perder informação — a sugestão é **oferecida**, não imposta.
O utilizador vê o que foi corrigido e decide.

## Abertura de documentos

Cada resultado é agora uma ligação para `/documento?id=N`, com o fragmento
`#page=N` quando aplicável — os visualizadores de PDF dos navegadores saltam
diretamente para a página certa.

### Resolver a origem

O campo `origem` codifica três informações:

```
data/raw/psi9/Fisica-Quimica/Sebenta.zip!Sebenta modulo F5.pdf#pagina=2
└────────────── ficheiro ──────────────┘ └── dentro do zip ──┘ └ pagina ┘
```

`_resolver_origem()` separa as três partes; `_ler_arquivo()` lê do disco ou
de dentro do ZIP (em memória, sem extrair).

### Segurança: nunca aceitar caminhos do utilizador

O parâmetro da URL é o **id do documento**, nunca um caminho. O servidor
consulta a base de dados para obter a origem. Se aceitasse um caminho,
`/documento?path=../../../Windows/System32/config/sam` seria um ataque de
**path traversal**.

Defesa em profundidade, mesmo assim: `_ler_arquivo()` resolve o caminho
absoluto e verifica que está **dentro de `data/raw`**; caso contrário levanta
`PermissionError`.

Testado: id inexistente devolve 404, tentativa de travessia devolve 400,
ficheiro apagado devolve 410.

## Refactor do retorno da busca

`buscar_detalhado()` deixou de devolver uma tupla que ia crescendo
(`resultados, modo`) e passou a devolver um registo `ResultadoBusca` com
`documentos`, `modo` e `sugestoes`. Lição: quando uma tupla de retorno chega
a três elementos, é sinal de que falta um nome ao conceito.
