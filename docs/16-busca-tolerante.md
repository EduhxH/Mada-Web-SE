# Busca tolerante: quórum, correção automática e peso do título

Problema: a busca era **binária**. Ou um documento tinha *todos* os termos, ou
caía-se no OU e vinha *tudo* o que tivesse *algum*. Não havia meio-termo, e o
utilizador tinha de acertar nas palavras exatas.

## 1. Quórum: um degrau entre "todos" e "qualquer"

Três níveis, tentados por ordem:

| Nível | Exige | Quando |
|---|---|---|
| **todos** | os q termos | primeira tentativa (interseção rápida) |
| **quórum** | `max(2, ceil(0.6 × q))` | quando "todos" falha |
| **algum** | 1 termo | último recurso |

O relaxamento é progressivo: com 4 termos tenta 4, depois 3, depois 2, depois
1 — para no primeiro nível que devolve resultados.

O truque de implementação: uma **única passagem de contagem** dá todos os
níveis de uma vez.

```python
contagem = Counter()
for postings in postings_por_termo.values():
    contagem.update(postings.keys())   # quantos termos cada doc tem
```

A interseção rápida (menor lista primeiro) fica para o caso "todos", que
tem curto-circuito e não precisa de percorrer as listas grandes.

### Efeito medido

| Consulta | Antes (E→OU) | Depois (quórum) |
|---|---|---|
| ficha de exercicios de matematica | 118 | **11** (2 de 3) |
| horario da turma psi9 | 167 | **100** (2 de 3) |

Não é "menos resultados", é **menos lixo**: os que caem satisfaziam apenas 1
dos 3 termos.

## 2. Correção automática de gralhas óbvias

Antes, uma gralha dava zero resultados e uma sugestão para clicar. Agora, se a
correção for **muito confiante**, é aplicada logo:

- distância de edição **1** (uma letra trocada, faltando ou a mais), e
- a palavra sugerida existe em pelo menos **3 documentos**

`matematca exercicios` → corrige para `matematica exercicios` → 6 resultados.

A interface diz o que fez, com escapatória:

> A mostrar resultados para **matematica exercicios** · *pesquisar antes por
> matematca*

O link acrescenta `exato=1`, que desliga correção e relaxamento — o
utilizador manda sempre. Tudo o que não cumpre os dois critérios continua a
ser apenas uma sugestão.

## 3. Peso do título

Um acerto no título vale mais que no corpo: **o título diz o que o documento
é, o corpo só diz o que ele menciona**.

```python
fator = 1 + 0.6 * (termos_no_titulo / termos_da_consulta)
```

Aplicado **depois** do ranqueamento, sobre os documentos já carregados —
custo zero de I/O extra.

| Consulta | Antes | Depois |
|---|---|---|
| regulamento interno | pontuação 0.06, disperso | **REGULAMENTO INTERNO APROVADO** em 1.º, 1.66 |
| sebenta fisica | disperso | **Sebenta modulo F5** em 1.º e 2.º |

## Limite que fica

`horario da turma psi9` continua a não pôr o horário em primeiro. O documento
chama-se "horarios - pagina 12" e a consulta diz "horario" — o realce de
título não dispara porque **singular e plural são termos diferentes**.

É a mesma limitação de sempre, agora visível num sítio novo. Resolvê-la exige
stemming (destrói informação no índice) ou um dicionário morfológico. A
sugestão ortográfica cobre o caso quando o termo não existe de todo; aqui
existe, e por isso nem sugestão há.
