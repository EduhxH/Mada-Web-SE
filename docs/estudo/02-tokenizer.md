# Estudo linha a linha — Sessão 2: app/indexing/tokenizer.py (Etapa 5)

## Conceitos da etapa

- **Texto bruto → normalização**: colapsar variações irrelevantes numa forma
  única. Ordem deliberada: minúsculas → acentos → extração → stop words.
  Toda normalização é uma TROCA: recall (achar mais) por precisão
  (distinguir menos). Ex.: .lower() une "Python/PYTHON", mas funde
  "Bush"/"bush".
- **Unicode/acentos**: cada caractere tem um code point; NFKD decompõe
  acentuado em base + marca combinante ("ç" → "c" + U+0327); descartamos as
  marcas via `unicodedata.combining()`. Sem tabela manual de á→a.
- **Token vs. termo**: token = ocorrência individual extraída (ordem e
  repetições preservadas — alimentam o TF); termo = unidade normalizada do
  vocabulário do índice.
- **Stop words**: palavras onipresentes (IDF ≈ 0) ficam fora do índice.
  Custo: "to be or not to be" fica impesquisável — decisão consciente.
- **Stemming vs. lematização** (não implementados): stemming corta sufixos
  por regra bruta ("melhores" → radical "melhor"; barato, erra); lematização
  usa dicionário morfológico e chega à forma de dicionário ("melhores" →
  "bom"; caro, preciso). Hoje "programação" ≠ "programador" no índice.

## Pontos do código

- `STOP_WORDS = frozenset("""...""".split())` — string tripla → `.split()`
  quebra por qualquer espaço em branco → frozenset: teste `in` O(1) médio,
  imutável por ser constante de módulo. A lista está gravada JÁ normalizada
  ("nao", "voce") porque o filtro roda DEPOIS da remoção de acentos;
  `test_stop_words_estao_normalizadas` garante isso.
- `_PADRAO_TOKEN = re.compile(r"[a-z0-9]+")` — `_` = privado por convenção;
  `r"` = raw string; compilar no módulo paga o parsing do regex UMA vez, na
  importação. (Nuance honesta: o `re` tem um cache interno de padrões, então
  compilar dentro da função não re-parsearia sempre — mas pagaria a consulta
  ao cache a cada chamada e ficaria sujeito a despejo; no módulo o custo é
  garantido e a intenção, explícita.)
- `[a-z0-9]+` — classe de caracteres + quantificador "uma ou mais". Roda pós
  normalização, então cobre tudo que interessa. Limite honesto: CJK,
  cirílico e emoji desaparecem em silêncio — escopo pt/en, não lei.
- `remover_acentos` — NFKD + generator + `"".join` (strings são imutáveis).
- `tokenizar(texto, remover_stop_words=True)` — parâmetro padrão cria o modo
  que preserva stop words (usado pelo gerar_trecho do main.py). `findall`
  preserva ordem e repetições. Custo O(c) tempo e espaço, c = caracteres.
- `tokenizar(None)` → AttributeError: anotação de tipo não protege.

## Verdades verificadas no exercício

1. Trace de "A Programação NÃO é difícil!": lower → sem acentos →
   `['a','programacao','nao','e','dificil']` → filtro →
   `['programacao','dificil']`.
2. Compilar fora da função = parsing do regex uma vez na inicialização, em
   vez de custo extra a cada página indexada e a cada consulta.
3. "3.11" → tokens '3' e '11' (o ponto é separador); "é" → "e" → stop word.
4. Stop words COM acento seriam um bug silencioso: "não" vira "nao" no texto,
   `"nao" in {"não",...}` dá False, stop words vazam para o índice.
   Pego por `test_stop_words_estao_normalizadas`.

## Sobre notação: O(n) vs O(c)

O(n) e O(c) aqui são a MESMA afirmação — o que muda é a letra escolhida.
Regra da Etapa 3: declare o que a letra conta. No projeto reservamos `n`
para "número de documentos", então usamos `c` (caracteres) no tokenizer
para evitar ambiguidade. Big O não se decora de lista: deriva-se contando
a operação dominante — quem explica "parseia uma vez vs. a cada chamada"
já sabe derivar.
