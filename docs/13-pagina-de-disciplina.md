# Página de disciplina

Problema: escolher "Matemática" sem escrever nada dava um **ecrã vazio**. O
utilizador tinha de adivinhar o que procurar.

Agora, disciplina sem consulta mostra pontos de partida.

## Temas frequentes: TF-IDF ao nível da disciplina

Listar as palavras mais comuns não serviria — dariam palavras genéricas. O
que queremos são termos **característicos** daquela disciplina.

Reutilizámos a ideia do IDF:

```
pontuacao(termo) = cobertura x especificidade

cobertura      = docs da disciplina com o termo / docs da disciplina
especificidade = log(total de docs / docs com o termo em toda a colecao)
```

Um termo presente em toda a coleção tem `especificidade = log(1) = 0` e
desaparece. Um termo presente em boa parte da disciplina e raro fora dela
sobe ao topo.

## O filtro que fez a diferença: teto de cobertura

A primeira versão devolvia lixo:

```
TIC   -> tic, pretendida, ismaelcosta, autorais, violacao, formador
Escola -> uploads, wp, content, escola, formacao
```

Diagnóstico: eram **boilerplate**. O rodapé de copyright estava em 95% dos
slides de TIC; `wp/uploads/content` vinha dos URLs do WordPress. Como são
específicos da disciplina *e* aparecem em quase todos os documentos dela,
pontuavam altíssimo.

A percepção que resolveu: **um tema que aparece em mais de metade dos
documentos não distingue nada dentro da disciplina** — é cabeçalho, rodapé
ou modelo. `COBERTURA_MAXIMA = 0.5`.

Mais três filtros pequenos: fora o nome da própria disciplina (já foi
escolhida), termos com menos de 4 letras, números puros, e uma lista curta de
ruído técnico (`wp`, `uploads`, `http`...).

Resultado:

| Disciplina | Antes | Depois |
|---|---|---|
| Física-Química | quimica, fisica, f3, modulo | **radiacao, temperatura, onda, termodinamica, calor** |
| TIC | tic, ismaelcosta, autorais, violacao | **tratamento, metodos, normalizada, dados, blender** |
| Escola | uploads, wp, content | **atividades, plano, curso, projeto, adultos** |

Nota honesta: Horários devolve abreviaturas (`comp`, `port`, `psic`) porque é
literalmente o que a tabela do horário contém. O algoritmo está certo; o
documento é que é assim.

## Desempenho: 1322 ms -> 89 ms

A primeira consulta usava uma subconsulta correlacionada — uma contagem por
cada termo, milhares de vezes. Substituída por duas consultas simples
(df na disciplina, df global) combinadas em Python, mais dois índices novos
(`postings(doc_id)` e `documents(disciplina)`).

Por cima disso, cache em memória com chave `(disciplina, total de
documentos)` — muda o corpus, a chave muda e a cache invalida-se sozinha.
Segunda visita: **1 ms**.

## As outras secções

- **A turma procurou por** — consultas populares *nessa disciplina*, com o
  mesmo limiar de 2 participantes das sugestões.
- **Mais abertos nesta disciplina** — cruzamento entre os eventos de abertura
  e a disciplina de cada documento. Como o registo de uso e o índice são
  ficheiros SQLite separados, não há JOIN: buscam-se os doc_ids mais abertos,
  depois as disciplinas desses ids, e filtra-se em Python.
- **Documentos com mais conteúdo** — sempre presente, para a página nunca
  ficar vazia antes de haver dados de utilização.

Cada tema é uma ligação para `/?q=<tema>&d=<disciplina>` — clicar leva a uma
busca real dentro da disciplina. Verificado: "sebenta" em Física-Química dá
48 resultados; "tratamento" em TIC dá 84.
