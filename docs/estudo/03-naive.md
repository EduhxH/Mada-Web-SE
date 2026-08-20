# Estudo linha a linha — Sessão 3: app/search/naive.py

## Pontos do código

- Imports entre módulos do pacote (`app.indexing.tokenizer`): pontos no lugar
  de barras. Importar `tokenizar` de um único lugar materializa o invariante:
  consulta e documento passam pela MESMA normalização.
- `list[Documento]` — genérico embutido (Python 3.9+); documentação
  verificável, não barreira de execução.
- `if not termos: return []` — coleção vazia é falsy; padrão guard clause.
  Sem ele: `all()` sobre sequência vazia retorna True (verdade por
  vacuidade) e a busca vazia devolveria a COLEÇÃO INTEIRA. O guard é decisão
  semântica ("pergunta nenhuma → resposta nenhuma"), pregada no chão por
  `test_consulta_vazia_ou_so_stop_words`.
- `set(tokenizar(doc.texto))` — lista → conjunto: presença O(1) médio.
  Construção O(m) uma vez + q testes O(1) = O(m + q) por doc; com lista
  seria O(q × m). Roda DENTRO do laço: retokeniza cada doc a cada consulta —
  o desperdício que o índice invertido elimina.
- `all(gerador)` — curto-circuito: para no primeiro False. Lógica E.
  Melhora a constante, não a classe: o custo dominante da iteração é a
  tokenização O(m), paga antes de qualquer teste.
- Retorno na ordem da coleção: encontra, não ranqueia. Aceitável para
  oráculo (só o CONJUNTO importa), inaceitável para produto (relevância).
- Argumentos trocados não são barrados na chamada: falham dentro, com
  AttributeError (lista não tem .lower). Reforço da Sessão 1: anotações não
  validam nada em execução.

## Custos

Tempo O(n × m) por consulta (retokenização domina); espaço O(n + m).
Melhor ≈ pior caso: mesmo sem nenhum resultado, tudo é tokenizado.
