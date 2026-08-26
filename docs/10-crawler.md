# Crawler do site da escola

`python main.py rastrear https://www.sefo.pt/ --paginas 300 --profundidade 3`

Resultado da primeira corrida: **207 páginas guardadas, 270 pedidos HTTP,
306 s**. O site esgotou antes do limite de 300.

## Separação de responsabilidades

O crawler **não interpreta HTML**. Ele descobre URLs, descarrega e guarda os
ficheiros em `data/raw/Escola/`. Quem extrai texto é o `local_source`, que
aprendeu `.html`. Isto respeita a separação da Etapa 1 (crawler != parser) e
tem uma vantagem prática: **reindexar não volta a rastrear**.

## O ciclo principal

Busca em largura (BFS) com duas estruturas:

- `fronteira`: `deque` de `(url, profundidade)` — FIFO, portanto explora
  camada a camada a partir da semente.
- `relatorio.visitadas`: `set` — impede repetir e impede ciclos (páginas que
  se linkam mutuamente).

Guardas antes de cada pedido, **por ordem crescente de custo**:

1. já visitada? (memória)
2. mesmo domínio? (string)
3. é página e não recurso? (extensão)
4. dentro da profundidade?
5. `robots.txt` permite? (objeto já carregado)

Só depois de as cinco passarem é que há rede. Nunca se gasta um pedido HTTP
para descobrir algo que se sabia de graça.

## Boa educação

- `robots.txt` lido com `urllib.robotparser` (biblioteca padrão). Se declarar
  `Crawl-delay`, o intervalo passa a ser o maior dos dois.
- Intervalo mínimo de 1 s entre pedidos, medido com `time.monotonic()`:
  espera-se apenas o que falta desde o pedido anterior, não 1 s fixo.
- `User-Agent` identifica o robô honestamente.
- Só `www.sefo.pt`; ligações externas são descartadas.

## O sitemap

`sitemap_index.xml` -> sub-sitemaps -> URLs, tudo com `xml.etree` da
biblioteca padrão. As URLs entram na fronteira com **profundidade 0**: são
páginas que a escola declara como suas, não descobertas por acaso.

Não substitui seguir ligações — apanha páginas que o sitemap não lista.

## Como a URL sobrevive até ao resultado

Problema: guardar em disco perderia a URL, e o resultado apontaria para um
ficheiro local em vez da página real.

Solução: ao guardar, injeta-se `<meta name="madalena-origem" content="URL">`
no `<head>`. O `local_source` lê essa marca e usa-a como `origem`; usa também
o `<title>` real como título. Assim `doc.origem` é a URL e o resultado liga
diretamente ao site.

Nome do ficheiro: caminho da URL limpo + hash MD5 de 8 caracteres da URL
completa — legível e sem colisões.

## Extração de texto

`BeautifulSoup` com `html.parser` (sem dependências extra). Remove-se
`script`, `style`, `nav`, `header`, `footer`, `noscript` — senão o menu do
site apareceria em todas as 207 páginas e o IDF desses termos cairia a zero,
poluindo o índice.

## Correções que a integração revelou

1. **Disciplina colapsada**: `_disciplina` usava a *primeira* pasta do
   caminho relativo, portanto `psi9/Matemática/x.pdf` virava "psi9". Passou a
   usar a pasta **imediatamente acima do ficheiro**.
2. **Ligações partidas**: resultados do site tinham `origem` = URL, mas o
   link apontava para `/documento?id=N`, que procura um ficheiro local.
   Agora, se a origem começa por `http`, o link vai direto ao site
   (com `rel="noopener"`).
3. **Livro fora do índice**: `arquitetura-limpa.pdf` foi movido para
   `data/livros/` — não é material escolar e tem direitos de autor.

## Estado do índice

**994 documentos, 13.235 termos, 12 disciplinas** (11 do PSI9 + "Escola").

## Por explorar

51 ligações foram descartadas por "não é HTML" — em boa parte **PDFs
publicados no site** (regulamentos, listas de manuais). São conteúdo útil que
hoje fica de fora: o crawler descarrega-os e deita fora por causa do
`Content-Type`. Guardá-los seria uma extensão pequena.

## Segunda corrida: PDFs incluídos

`--paginas 400` -> **258 guardadas (207 HTML + 51 PDF)**, 270 pedidos, 273 s.
Só 12 ignoradas, todas por estado HTTP.

Indexado: **1797 documentos** (os 51 PDFs deram 803 páginas). A disciplina
"Escola" passou de 207 para 1010 documentos.

### O problema do PDF: não dá para injetar metadados

Nas páginas HTML a URL sobrevive via `<meta name="madalena-origem">`. Num PDF
isso não é possível sem reescrever o ficheiro.

Solução: um **manifesto** `_origens.json` na pasta, mapeando nome de ficheiro
-> URL. O `local_source` lê-o por pasta (uma vez, em cache) e usa-o como
`origem`; o próprio manifesto é saltado na indexação. Se estiver corrompido,
a carga continua com o caminho local — falha suave, não exceção.

Funciona para HTML e PDF, e a marca no `<head>` fica como redundância.

### Fragmento de página

O `local_source` gera `#pagina=N`. Os navegadores entendem `#page=N`. Como a
origem agora pode ser uma URL, o `_ligacao` converte:

```python
return doc.origem.replace("#pagina=", "#page=")
```

Resultado: pesquisar "regulamento interno" devolve
`.../REGULAMENTO-INTERNO-APROVADO-ABRIL-2024.pdf#page=1` — o PDF real da
escola, aberto na página certa.
