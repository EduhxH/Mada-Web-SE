# Secções nos resultados

Problema: uma pesquisa devolvia tudo numa lista única. Com 1.797 documentos
de naturezas diferentes — 850 páginas do site, 610 fichas e materiais, 295
regulamentos, 42 horários — o aluno não distinguia "isto é uma ficha da minha
disciplina" de "isto é uma notícia do site da escola".

## As quatro secções

| Secção | Regra |
|---|---|
| **Horários** | disciplina é Horários |
| **Regulamentos e informações** | título casa regulamento, critérios, planificação, matriz, circular, comunicado, edital, ata… |
| **Páginas do site** | origem é um URL |
| **Fichas e materiais** | tudo o resto |

A ordem das regras importa: um PDF de regulamento vindo do site vai para
*Regulamentos*, não para *Páginas do site* — porque a regra do título é
avaliada primeiro. O que interessa ao aluno é o que o documento **é**, não de
onde veio.

### Fronteiras de palavra

A classificação usa expressões regulares com `\b`, não `LIKE '%ata%'`. Sem
isso, "ata" apanharia "d**ata**" e "Tratamento de **Dat**os" seria
classificado como regulamento. Há um teste para exatamente esse caso.

## Ordenação: a secção do melhor resultado vem primeiro

As secções não têm ordem fixa. São ordenadas pela **melhor pontuação que
contêm**, de forma que a secção do resultado mais relevante lidere.

Verificado: `horarios` devolve 81 resultados e a secção *Horários* aparece em
primeiro com 42; `avaliacao` devolve 257 e lidera *Regulamentos* com 142.

Dentro de cada secção, a ordem de relevância é preservada.

## Quando NÃO agrupar

Se todos os resultados caem numa só secção, os cabeçalhos não aparecem —
seria ruído. Verificado: `arrays` devolve 9 resultados, todos "Fichas e
materiais", e a página mostra uma lista simples.

## Ver tudo de uma secção

Cada secção mostra 5 resultados. Se tiver mais, o cabeçalho traz "ver os N",
que leva a `/?q=...&s=<seccao>` — a mesma secção sem limite, com uma ligação
de volta. O parâmetro é validado contra as secções conhecidas antes de ser
usado.

## Bónus: títulos legíveis nos documentos rastreados

Ao testar, os PDFs do site apareciam como:

```
wp-content-uploads-REGULAMENTO-INTERNO-APROVADO-abc12345
```

O título vinha do nome do ficheiro guardado, que é derivado do caminho do URL
com um hash à mistura. Agora deriva-se do **último segmento do URL**:

```
REGULAMENTO INTERNO APROVADO ABRIL 2024
Criterios Avaliacao TIC
```

Não é cosmética apenas: o título é indexado, portanto isto melhora também a
pesquisa por nome de documento.
