# Sugestões na barra de pesquisa

Resolve o problema de fundo: **o utilizador tem de adivinhar as palavras
certas**. Se não for certeiro, não encontra.

## Três fontes, por ordem de prioridade

| Fonte | O que é | Porque vem nesta ordem |
|---|---|---|
| `historico` | consultas que **este** participante já fez | o que a pessoa procurou antes é o melhor previsor do que procura agora |
| `popular` | consultas que **outros** fizeram | descoberta: mostra o que a turma anda a procurar |
| `vocabulario` | termos reais do índice | rede de segurança: nunca sugere palavra que não existe no corpus |

O vocabulário completa **apenas a última palavra**: escrever `ficha mate`
sugere `ficha matematica`, não substitui a frase toda.

## Regras que evitam sugestões inúteis

- **Só consultas que deram resultados.** Sugerir uma pesquisa que devolve zero
  seria enviar a pessoa contra uma parede. Filtro: `resultados > 0`.
- **Nunca sugerir o que já está escrito.** Se o campo diz `matematica`, não
  faz sentido sugerir `matematica`.
- **Sem duplicados entre fontes.** A mesma consulta pode estar no histórico e
  ser popular; aparece uma vez, com a origem de maior prioridade.
- **Mínimo de 2 caracteres** antes de pedir seja o que for.

## Privacidade: o limiar de dois participantes

Com 8 beta testers, uma consulta feita por **uma** pessoa identifica essa
pessoa. Se aparecesse como "popular" a outro participante, estaríamos a
revelar o que um colega pesquisou.

Por isso o `HAVING COUNT(DISTINCT participante) >= 2`: uma consulta só entra
nas populares quando pelo menos duas pessoas a fizeram. É o princípio de
*k-anonimato* aplicado ao caso mais pequeno possível.

Verificado: aluno-01 pesquisa "horarios turma"; aluno-02 escreve "hora" e
**não** vê essa consulta.

## Segurança: escapar o LIKE

O prefixo entra numa cláusula `LIKE`. Em SQL, `%` casa com qualquer coisa e
`_` com qualquer caractere — se um utilizador escrevesse `%`, o padrão
`'%%'` casaria com **todas** as consultas de toda a gente, furando o filtro
de prefixo.

`escapar_like()` neutraliza `%`, `_` e `\`, e as consultas usam
`ESCAPE '\'`. Os valores continuam a viajar por parâmetros `?` — o escape é
sobre o *conteúdo* do padrão, não sobre a estrutura do SQL.

## Interface

Dropdown por baixo do campo, com a origem à direita ("já pesquisou",
"popular"). Setas para navegar, Enter para escolher, Escape para fechar,
clique para selecionar.

Otimizações, pela mesma razão do preview:
- **160 ms de atraso** — escrever "matematica" dispararia 10 pedidos sem ele.
- **Não repete o último pedido** — se o texto não mudou, não pergunta outra vez.
- Só pede a partir de 2 caracteres.

## O que isto prepara

O `historico` e o `popular` saem ambos da tabela `eventos` que já existia —
não foi preciso guardar nada de novo. As mesmas consultas alimentam depois:
- a página de disciplina (o que procurar quando o ecrã está vazio)
- o "também procuraram por" (co-ocorrência na mesma sessão)
