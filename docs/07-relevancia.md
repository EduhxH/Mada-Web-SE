# Relevância: títulos indexados, busca OU e o factor de coordenação

Trabalho guiado por **medição**, não por opinião. O ponto de partida foram 8
consultas escritas como um aluno as escreveria.

## Diagnóstico (antes)

| Consulta | Resultados |
|---|---|
| ficha de exercicios de matematica | **0** |
| horario da turma psi9 | **0** |
| criterios avaliacao portugues | **0** |
| sebenta | **0** |
| trabalho de grupo fisica | 8 |
| exercicios | 35 |

Duas causas distintas:

1. **Lógica E demasiado estrita** — `exercicios` sozinho dava 35 resultados,
   mas `ficha de exercicios de matematica` dava zero: o E exige que *um mesmo
   documento* contenha todos os termos. **Acrescentar palavras piorava a
   busca**, o oposto do que o utilizador espera.
2. **Títulos não indexados** — 48 documentos chamados "Sebenta modulo F5"
   existiam no índice, mas a palavra `sebenta` não constava do índice
   invertido: `construir_indice` só tokenizava `doc.texto`.

## Correções

### Título e disciplina passam a ser pesquisáveis

`Documento` ganhou a propriedade `texto_pesquisavel`:

```python
@property
def texto_pesquisavel(self) -> str:
    return f"{self.titulo} {self.disciplina} {self.texto}"
```

Usada **tanto** pelo `inverted_index` como pelo `naive` — a mesma disciplina
do `tokenizar`: uma única definição partilhada, senão o oráculo divergiria.
Vocabulário: 9196 -> 9273 termos.

### Busca OU com recurso

Se o E não devolve nada (e há mais de um termo), tenta-se a **união** das
posting lists em vez da interseção. Princípio: **nunca devolver vazio quando
alguma coisa corresponde**.

```python
candidatos = _intersecao(postings_por_termo)   # E
if not candidatos and permitir_ou:
    candidatos = _uniao(postings_por_termo)    # OU
```

`buscar_detalhado()` devolve `(resultados, modo)` para a interface poder
avisar "correspondências parciais". `buscar()` mantém a assinatura antiga.

**O código morto ganhou vida:** o `if freq is None: continue` do ranker, que
com lógica E nunca era executado, passa a ser essencial — no modo OU um
candidato pode não conter todos os termos.

**O oráculo continua estrito:** o teste de integração chama
`buscar(..., permitir_ou=False)`, garantindo que a semântica E não mudou.

### Factor de coordenação

Com OU, um documento que satisfaz 3 de 4 termos deve vencer um que satisfaz
1 de 4 — mesmo que esse tenha um termo raro de alto IDF. Por isso a pontuação
é multiplicada por `termos_encontrados / total_de_termos`.

Detalhe elegante: **no modo E o factor é sempre 1** (todos os candidatos têm
todos os termos), portanto não altera nada do comportamento anterior.

## Resultado (depois)

| Consulta | Antes | Depois | Modo |
|---|---|---|---|
| ficha de exercicios de matematica | 0 | 118 | parcial |
| horario da turma psi9 | 0 | 167 | parcial |
| criterios avaliacao portugues | 0 | 82 | parcial |
| sebenta | 0 | **48** | E |
| trabalho de grupo fisica | 8 | 20 | E |
| exercicios | 35 | 57 | E |

Zero consultas vazias. `sebenta` devolve as 48 páginas certas, no topo.

## O problema seguinte, revelado pela medição

`horario da turma psi9` devolve 167 resultados, mas o topo **não** é o
documento de Horários. Investigação:

```
"horario"  -> 0 documentos
"horarios" -> 43 documentos
```

**Singular e plural são termos diferentes.** É exactamente o problema de
*stemming* descrito na Etapa 5 e deliberadamente adiado. Procurar "horarios"
funciona perfeitamente; "horario" não encontra nada.

Segundo problema relacionado: no modo OU, uma consulta de 4 palavras onde só
uma corresponde ainda devolve muitos resultados fracos. O factor de
coordenação ajuda a ordenar, mas não filtra.

Caminhos possíveis (decisão pendente):
- **Stemming** — resolve singular/plural, mas é lossy (pode fundir palavras
  distintas).
- **Exigir uma fracção mínima dos termos** no modo OU (ex.: metade).
- **Limitar o modo OU aos termos mais raros** (ignorar os de IDF baixo).
