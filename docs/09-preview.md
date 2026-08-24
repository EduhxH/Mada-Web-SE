# Pre-visualização de resultados

Objetivo: responder a "é este o documento que eu quero?" **sem abrir nada**.

## A decisão de desenho mais importante: hover não existe no telemóvel

Os alunos usam telemóvel, computador e o telão da sala. Passar o rato por
cima só funciona em dois desses três — num ecrã tátil não há "por cima".

Uma pre-visualização só com hover **desapareceria no dispositivo mais usado**.
Por isso são dois gatilhos para o mesmo conteúdo:

| Largura | Gatilho | Apresentação |
|---|---|---|
| > 1024px | hover (350 ms de atraso) | painel flutuante à direita |
| <= 1024px | botão "prever" | expande dentro do resultado |

O CSS decide qual existe (`@media`), o JavaScript respeita a mesma fronteira.

## O que o painel mostra

1. **Metadados** — disciplina, tipo, página/slide, número de palavras.
   Responde a "que documento é este?", que o título muitas vezes não diz:
   `Guiões e Fichas de Trabalho(2)` não diz nada; "Física-Química · PDF ·
   página 11 · 192 palavras" diz.
2. **Ficheiro de origem** — e, quando aplicável, o ZIP que o contém.
3. **Excerto longo** — `raio=55` palavras em vez de 12. Medido num documento
   real: **170 -> 716 caracteres, 4,2x mais contexto**, com os termos da
   consulta destacados.

Deliberadamente **sem miniatura do PDF** por agora. Um `<iframe>` com o
visualizador do navegador é lento a arrancar e traz barras de ferramentas
próprias; o texto é instantâneo e nunca falha. Fica como camada opcional.

## Otimizações (a razão de existirem)

- **Atraso de 350 ms** — sem ele, arrastar o rato pela lista dispara 20
  pedidos ao servidor. O atraso distingue "passar por cima" de "querer ver".
- **Cache no cliente** — `cache[id]` guarda o fragmento; voltar ao mesmo
  resultado é instantâneo e não gera pedido.
- **Carregamento preguiçoso** — nada é pedido antes de haver intenção. A
  página de resultados continua com o mesmo peso de antes.

Sem isto, uma funcionalidade de conforto tornaria a busca mais lenta — o
oposto do objetivo.

## Segurança

O endpoint `/preview?id=N` segue a mesma regra do `/documento`: **o parâmetro
é o id, nunca um caminho**. O servidor consulta a base de dados.

E como o fragmento é HTML construído a partir de texto de PDFs (conteúdo que
não escrevemos), tudo passa por `html.escape`. Há um teste que injeta
`<script>` no texto de um documento e exige que saia escapado — um PDF
malicioso não executa código no navegador de quem pesquisa.

## Estrutura

`app/interface/preview.py` — `resolver_origem()`, `descrever()`, `fragmento()`.
Separado do `web.py` porque é lógica de apresentação testável sem servidor:
os 10 testes de `test_preview.py` não abrem sockets.
