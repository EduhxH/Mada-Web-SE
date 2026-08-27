# Expansão morfológica da consulta

## O problema, medido

| | |
|---|---|
| Vocabulário duplicado por número (singular/plural) | **25%** — 2.283 pares |
| `criterio` vs `criterios` | perde-se **97%** dos documentos |
| `horario` vs `horarios` | perde-se **63%** |
| `ficha` vs `fichas` | perde-se **55%** |

O motor **compreendia** perfeitamente `horario da turma psi9` — extraía os
três termos, encontrava documentos, filtrava por quórum. O que falhava era
que `horario` e `horarios` são strings diferentes.

## Expansão, não stemming

| | Stemming | Expansão da consulta |
|---|---|---|
| Onde atua | no índice, na indexação | na consulta, em tempo real |
| `horarios` fica guardado como | `horari` (mutilado) | `horarios` (intacto) |
| Reversível | não, é preciso reindexar | sim, muda-se uma constante |
| Se errar | corrompe a busca toda, em silêncio | um resultado a mais, visível |

Com stemming, `radiação` e `radiar` colapsariam no mesmo termo e nunca mais
se distinguiriam. Aqui o índice continua exato e é a **pergunta** que fica
mais generosa.

## As regras geram, o vocabulário decide

O mesmo princípio da deteção de verbos (*"aumenta é verbo porque aumentar
existe no índice"*):

| Regra | Exemplo |
|---|---|
| `+s` | ficha → fichas |
| `+es` (após r, z, s) | professor → professores, luz → luzes |
| `-l` → `-is` | papel → papeis |
| `-m` → `-ns` | homem → homens |
| `-ao` → `-oes/-aos/-aes` | licao → licoes |

E todas as inversas, para quem escreve o plural. **Nenhum candidato entra sem
existir no índice**, por isso é impossível expandir para palavras inventadas —
`psi9` → `psi9s` não existe, logo não expande.

As postings de cada termo passam a ser a **união das variantes**, com
frequências somadas (correto para o TF) e `df` a contar documentos com
qualquer variante (correto para o IDF: o conceito "horário(s)" é mesmo mais
comum do que a forma singular sugeria).

## Resultado

| Consulta | Sem expansão | Com expansão | Modo |
|---|---|---|---|
| criterio | 3 | **108** | todos |
| horario | 42 | **113** | todos |
| ficha | 37 | **82** | todos |
| horario da turma psi9 | 0 | **2** | todos |
| ficha de exercicios de matematica | 0 | **5** | todos |
| arrays em visual studio | 0 | **3** | todos |

E o caso que motivou tudo:

```
"horario da turma psi9"
  1. [Horários] horarios - pagina 12     <- o horario do PSI9
  2. [Escola]   Plano Anual de Atividades
```

Repare-se no detalhe: várias consultas passaram de **vazio ou quórum** para
**"todos os termos"**. Ganhou-se recall *e* precisão ao mesmo tempo — os
documentos encontrados satisfazem agora todos os termos, em vez de dois em
três.

**Nada piorou**: `criterios avaliacao portugues` ficou nos mesmos 23,
`regulamento interno` 79→81, `sebenta fisica` 48→49.

## Duas descobertas ao escrever os testes

**O mínimo de 4 letras era redundante.** Tinha-o posto para evitar expansões
disparatadas (`as` → `ase`), mas a validação contra o vocabulário já faz esse
trabalho — `ase` não existe no índice. Baixou para 3, o que recupera palavras
reais como `luz`, `voz`, `paz`.

**O realce de título não salva pontuação zero.** Um teste falhou porque o
termo estava em 100% dos documentos do fixture: `IDF = log(1) = 0`, todas as
pontuações a zero, e o bónus multiplicativo de `1.6 × 0` continua zero. Num
corpus real isso quase nunca acontece, mas é uma propriedade a conhecer: o
realce **reordena**, não **ressuscita**.

## Custo

O vocabulário (18.135 termos) é carregado uma vez e mantido em cache com
chave no total de documentos — muda o corpus, a cache invalida-se sozinha.
Por consulta: ~6 verificações de pertença num conjunto por termo, e uma
consulta SQL extra por variante encontrada. Imperceptível.
