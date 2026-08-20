# Interface web local (app/interface/web.py)

Página de busca servida em `http://127.0.0.1:8080` por `python main.py web`.
Zero dependências novas: só `http.server` da biblioteca padrão.

## Decisões de projeto

- **Camada de interface sem lógica de busca**: o módulo só traduz HTTP em
  chamadas a `buscar()` e formata HTML — mesmo papel do `main.py` no
  terminal. O `gerar_trecho` foi movido para `app/search/snippet.py` para
  ser reutilizado pelas duas interfaces.
- **`ThreadingHTTPServer` + uma conexão SQLite por requisição**: conexões
  SQLite não podem ser compartilhadas entre threads; abrir/fechar por
  requisição é simples e seguro (custo irrelevante nesta escala).
- **Escapamento de HTML em tudo que vem de fora** (`html.escape` na
  consulta, títulos e trechos): sem isso, um documento ou uma consulta
  contendo `<script>` viraria código executando no navegador — o ataque
  clássico de XSS (cross-site scripting). Regra: todo texto que não é nosso
  é dado, nunca marcação.
- **`string.Template` em vez de f-string/format no HTML**: o CSS está cheio
  de chaves `{}`, que o `.format()` interpretaria como placeholders;
  `Template` usa `$nome` e não conflita.
- **Servidor amarrado a 127.0.0.1**: a interface só responde à própria
  máquina — não é um serviço exposto à rede.
- **Destaque dos termos**: cada palavra do trecho é normalizada com o MESMO
  tokenizer e comparada aos termos da consulta; casando, ganha `<b>`. O
  texto exibido preserva acentos e caixa do original.

## Estudo futuro

Quando chegarmos à etapa de HTTP no curso, este módulo vira material de
aula: request line, headers, status codes, Content-Type/Length e o ciclo
request→response estão todos visíveis aqui.
