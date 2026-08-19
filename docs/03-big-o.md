# Etapa 3 — Big O

Big O responde: **"se a entrada crescer, quão mais caro fica o algoritmo?"**
Não mede segundos (isso depende da máquina); mede a **forma do crescimento**.

## Vocabulário

- **Entrada**: o dado processado (coleção de docs, texto, fila de URLs, consulta).
- **n**: o tamanho da entrada — sempre declare **o que n conta**. No projeto
  usamos letras distintas: `n` documentos, `q` termos da consulta, `V` páginas
  visitadas, `p` tamanho de uma posting list, `k` candidatos no ranker.
- **Operação dominante**: a que mais se repete quando n cresce; Big O conta ela.
- **Complexidade temporal**: crescimento do nº de operações.
  **Espacial**: crescimento da memória extra. O índice invertido gasta espaço
  para economizar tempo.
- **Melhor / médio / pior caso**: busca em lista = O(1) / O(n) / O(n).
  Hash (set/dict) = O(1) médio, O(n) no pior caso (colisões patológicas).
- **Constantes são descartadas**: O(5n + 200) = O(n). Mas entre dois O(n),
  o de constante menor é mais rápido no relógio — Big O escolhe o algoritmo,
  constantes se otimizam depois.
- **Crescimento assintótico**: comportamento com n grande; com n pequeno,
  quase tudo serve.

## As classes

| Classe | n = 10 | n = 100 | n = 1.000 | n = 1.000.000 | No projeto |
|---|---|---|---|---|---|
| O(1) | 1 | 1 | 1 | 1 | `indice[termo]`, `url in visitadas` |
| O(log n) | ~3 | ~7 | ~10 | ~20 | busca indexada no SQLite (árvore B) |
| O(n) | 10 | 100 | 1.000 | 10⁶ | busca ingênua; tokenizar; varredura de tabela |
| O(n log n) | ~33 | ~700 | ~10⁴ | ~2×10⁷ | ranker ordenando candidatos |
| O(n²) | 100 | 10⁴ | 10⁶ | 10¹² | comparar cada doc com cada doc (evitar!) |
| O(2ⁿ) | 1.024 | ~10³⁰ | — | — | "testar todos os subconjuntos" (erro de modelagem) |
| O(n!) | 3,6×10⁶ | ~10¹⁵⁷ | — | — | "testar todas as ordenações" (idem) |

- **O(log n)**: cada passo corta o problema pela metade; dobrar n = +1 passo.
  A base do log não importa (vira constante).
- **O(n log n)**: classe da boa ordenação; "quase linear" na prática.
- **O(n²)**: laço dentro de laço sobre a mesma coleção grande = alarme.
  10× mais dados ⇒ 100× mais trabalho.

## Análises do motor

1. **Busca ingênua é O(n)**: verifica cada um dos n docs, a cada consulta.
   O defeito não é ler tudo — indexar também lê tudo — é ler tudo **de novo
   a cada consulta**.
2. **"Cada doc × cada termo" é O(n × q)**, não O(n²): laços sobre coleções
   diferentes. q é pequeno (2–4), então age como O(n) de constante maior.
3. **Dict O(1) ≠ consulta O(1)**: consulta completa = tokenizar O(q) +
   q buscas O(1) + **combinar postings O(p)** + ranquear O(k log k).
   O índice elimina o n global; o custo passa a depender de p e k.
   Termo raro = consulta voa; termo comum ("de") = posting list gigante.
   Big O de uma operação ≠ Big O do sistema: siga o dado pelo pipeline.
4. **Espaço do índice ≈ O(n)**: coleção dobra, postings dobram.
   (Curiosidade: o nº de termos *únicos* cresce mais devagar que a coleção —
   lei de Heaps — mas as postings dominam, e elas são lineares.)
