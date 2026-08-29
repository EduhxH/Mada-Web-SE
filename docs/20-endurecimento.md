# Endurecimento para exposição pública

Auditoria feita antes de expor o servidor à internet. O que se procurou:
acesso a páginas indevidas, injeção, negação de serviço, fuga de dados entre
participantes.

## O que já estava seguro

**SQL injection — não existe.** Todas as consultas usam parâmetros `?`. Há
duas f-strings em SQL e ambas foram verificadas:

- `WHERE id IN ({marcadores})` — `marcadores` é `?,?,?` construído a partir
  de uma **contagem**, nunca de dados
- `WHERE disciplina = ? {extra}` — `extra` vem de constantes do módulo

Nenhum valor de utilizador chega a ser concatenado numa instrução.

**Rotas — nega por omissão.** Qualquer caminho que não esteja na lista
devolve 403 ou 404. Verificado: `/estatisticas`, `/documento`, `/preview`,
`/sugerir`, `/abrir`, `/admin`, `/../etc/passwd` — todos 403 sem sessão.

**Travessia de caminho — bloqueada em dois níveis.** O parâmetro é um **id**,
nunca um caminho; e o leitor resolve o caminho absoluto e confirma que está
dentro de `data/raw`.

## O que estava vulnerável, e ficou corrigido

### 1. Injeção de cabeçalho pelo nome do ficheiro

```python
self.send_header("Content-Disposition", f'inline; filename="{nome}"')
```

`nome` vinha do ficheiro ou da entrada do ZIP. Um ficheiro chamado
`evil".pdf\r\nX-Coisa: sim` acrescentava cabeçalhos escolhidos por quem
preparou o ZIP — e os ZIPs vêm do Moodle, de fora.

Corrigido: `sanear_nome_ficheiro()` mantém apenas caracteres inócuos e corta
aos 120. Testado com quatro cargas maliciosas.

### 2. Força bruta nos códigos de acesso

Não havia limite de tentativas. Agora: **5 por 15 minutos** por endereço.
Verificado — bloqueia à 6.ª. Um código acertado limpa o contador, para não
penalizar quem se enganou a escrever.

### 3. Sem limite geral de pedidos

Assim que existe um URL público, bots encontram-no. Agora **120 pedidos por
minuto** por endereço (uma pessoa a pesquisar depressa faz ~20). Verificado:
bloqueia com 429.

**Detalhe importante atrás do túnel:** a ligação chega sempre de `127.0.0.1`,
e o endereço real vem em `CF-Connecting-IP`. Só se confia nesse cabeçalho
quando a ligação é mesmo local — caso contrário qualquer pessoa contornava o
limite forjando o cabeçalho. Há um teste para isso.

### 4. Ligações lentas (slowloris)

O servidor esperava indefinidamente por um pedido incompleto, prendendo uma
thread. Agora `timeout = 20` e `daemon_threads`, com as exceções de rede
apanhadas.

### 5. Fuga de privacidade entre participantes

`/estatisticas` estava aberta a qualquer participante autenticado, e a tabela
"consultas que falharam" não tinha limiar. Com 8 pessoas, uma consulta feita
por uma só identifica quem a escreveu — um colega via o que outro pesquisou.

Corrigido com um papel de **administrador**:

| | Participante | Administrador |
|---|---|---|
| Totais e gráficos | sim | sim |
| Consultas de 2+ pessoas | sim | sim |
| Consultas de uma só pessoa | **não** | sim |
| Tabela por participante | **não** | sim |

```
python main.py participantes --admin --criar 1
```

O investigador precisa do dado completo; os participantes não.

## Cabeçalhos de segurança

Enviados em todas as respostas:

| Cabeçalho | O que fecha |
|---|---|
| `X-Content-Type-Options: nosniff` | navegador adivinhar o tipo e executar HTML servido como outra coisa |
| `X-Frame-Options: DENY` | clickjacking (o site dentro de um iframe alheio) |
| `Content-Security-Policy` | scripts de terceiros, `eval`, plugins |
| `Referrer-Policy: no-referrer` | vazar o URL pesquisado para sites externos |
| `Permissions-Policy` | pedidos de câmara, microfone, localização |

## O que o túnel trata e nós não

Um DDoS volumétrico — milhões de pedidos — não se resolve em Python. Isso é
absorvido na borda do Cloudflare, antes de chegar à máquina. O que se defende
aqui é o abuso ao nível da aplicação: força bruta, varrimento, uma pessoa a
martelar um endpoint.

E há uma propriedade que vale sublinhar: **com o túnel, a Madalena continua
ligada a `127.0.0.1`**. Nada fica à escuta no IP público, nenhuma porta é
aberta no router, e o IP de casa nunca é revelado. É mais seguro do que
estava antes com `--host 0.0.0.0` na rede local.

## O que fica por fazer

- **Registo de acessos** — o servidor não regista pedidos. Com exposição
  pública convém saber o que chega (e o Cloudflare já dá parte disso).
- **Cookie `Secure`** — só faz sentido depois de HTTPS estar em uso.
- **Limpeza periódica do limitador** — `esquecer_antigos()` existe mas ainda
  não é chamado por temporizador; com poucos utilizadores não é urgente.
