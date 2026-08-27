# PLN: limpar os temas com POS, stop words e TF-IDF melhor

Diagnóstico inicial — os temas de Matemática eram quase todos verbos de
currículo:

```
dominios · reconhecer · propor · variavel · recorrendo · calculo · situacoes
· modelos · interpretar · reais · trabalhos · explorar · construcao ·
representacoes · autonomia · contribuir · analisar
```

Vinham de frases como *"o aluno deve reconhecer... propor situações...
recorrendo a modelos"*. Quatro camadas resolveram.

## 1. Etiquetagem morfológica por sufixo (`app/indexing/pos.py`)

Regras conservadoras para português, sem dependências nem modelos treinados:

| Classe | Sufixos | Exemplos apanhados |
|---|---|---|
| infinitivo | `-ar -er -ir -or` | reconhecer, propor, interpretar, analisar |
| gerúndio | `-ando -endo -indo` | recorrendo, utilizando |
| particípio | `-ado -ada -ido -ida` (+plurais) | normalizada, identificados |
| advérbio | `-mente` | rapidamente |
| conjugado | `-aram -assem -eriam` … | identificaram, resolveriam |

**O perigo das regras por sufixo** são os nomes que terminam como verbos:
*professor*, *lugar*, *calor*, *valor*, *computador*, *circular*, *estado*,
*conteúdo*, *velocidade*. Sem proteção, seriam todos despromovidos. Por isso
há listas de exceção (`NOMES_EM_AR`, `NOMES_EM_OR`, `NOMES_PARTICIPIO`…) e
23 testes que garantem que nomes reais sobrevivem.

Nota importante: a etiquetagem **só despromove candidatos a tema**. Uma
palavra mal classificada continua no índice e continua pesquisável.

## 2. Stop words *de tema* (não de indexação)

Cerca de 200 termos de vocabulário curricular e administrativo: `dominios`,
`competencias`, `objetivos`, `conteudos`, `criterios`, `avaliacao`,
`planificacao`, `modulo`, `atividades`, `situacoes`…

**Decisão deliberada: não foram para a lista de stop words do tokenizer.**
Se fossem, um aluno deixaria de poder pesquisar "critérios de avaliação" —
que é uma das buscas mais úteis que existem. São stop words apenas na
*sugestão de temas*, onde não ajudam ninguém a descobrir conteúdo.

## 3. Excluir documentos que não são de conteúdo

A descoberta mais reveladora: **Matemática tem 30 documentos, dos quais
apenas 3 são de conteúdo.** Os outros 27 são planificações e critérios de
avaliação — daí o vocabulário de currículo dominar.

Documentos administrativos são detetados pelo título (`planificacao`,
`criterios`, `justificacao`, `agenda`, `dossier`, `matriz`…) e ficheiros de
código-fonte pela extensão (`.cs`, `.designer`, `.resx`) — o vocabulário
destes é de identificadores (`txtnome`, `namespace`, `conn`), não de matéria.

Salvaguarda: só se excluem se sobrarem pelo menos 8 documentos de conteúdo.
Caso contrário a amostra ficaria pequena demais e recorre-se a tudo,
confiando nas camadas 1 e 2.

Comparação SQL sem acentos via função Python registada no SQLite
(`create_function("sem_acento", ...)`), para `Planificação` casar com
`planificacao`.

## 4. TF-IDF melhor: *lift* em vez de IDF global

Antes: `cobertura × log(total / df_total)`.

O problema é que `df_total` inclui os documentos da própria disciplina, o que
dilui o contraste. A medida certa compara a disciplina com **o resto**:

```
lift = (df_disc / n_disc) / (df_resto / n_resto)
pontuacao = cobertura × log(lift)
```

Termo com a mesma frequência dentro e fora: `lift = 1`, `log(1) = 0`, sai.
Exige-se ainda `lift >= 1.6`. Mantém-se o teto de cobertura de 0.5 (acima
disso é cabeçalho/rodapé) e o mínimo de 3 documentos.

Mais dois filtros pequenos: comprimento entre 4 e 16 caracteres (corta
`manualficheirostexto`) e nada com dígitos (corta `parte1`, `f3`, `p2`).

## Resultado

| Disciplina | Antes | Depois |
|---|---|---|
| Matemática | dominios, reconhecer, propor, recorrendo, situacoes | **variavel, calculo, geometria, variabilidade, amostra, outliers** |
| Português | (não existia) | **amor, farsa, cantigas, vicente, trovadoresca, personagens** |
| Física-Química | quimica, fisica, f3, modulo | **radiacao, onda, termodinamica, espectro, temperatura, calor** |
| PSI | manual, modular, disciplina, tgpsi | **forms, arrays, studio, windows, access, visual** |
| Arq. Computadores | — | **performance, reliability, nvidia, overclock, intel** |
| Educação Física | — | **motoras, coordenativas, condicionais, ginastica, saudavel** |

Ruído que resta, honestamente: `crie` (imperativo — o etiquetador não cobre
imperativos, e cobrir arriscaria nomes como *base*, *classe*, *arte*),
`indviduo` (gralha no documento original) e as abreviaturas de Horários, que
são o que a tabela realmente contém.

## Bónus: o bug do servidor fantasma

Ao verificar isto, os temas antigos continuavam a aparecer no navegador. Duas
instâncias estavam ligadas à porta 8080 — em Windows, `allow_reuse_address`
(ligado por omissão no `ThreadingHTTPServer`) deixa vários processos partilhar
a porta em silêncio, e os pedidos iam parar ao processo velho, com código
velho.

Corrigido: `allow_reuse_address = False` e mensagem clara ao arrancar. Agora
o segundo servidor recusa em vez de coexistir.


---

# Segunda ronda: o filtro que dispensa listas

Mesmo com POS e stop words curriculares, passava ruído: `muito`, `entao`,
`simples`, `reais`, `construcao`, `talvez`, `verdade`.

Crescer a lista à mão para sempre não é solução. O critério que resolve é
**corpus-driven**:

> Um termo que aparece em muitas disciplinas não distingue nenhuma.

Medido no corpus real (12 disciplinas):

| Termo | Disciplinas |
|---|---|
| simples | 9/12 |
| muito | 8/12 |
| entao · reais · construcao | 7/12 |
| **radiacao · cantigas · outliers · overclock** | **1/12** |
| **termodinamica · ginastica** | **2/12** |

A separação é limpa. Filtro: um tema tem de aparecer em no máximo **1/3** das
disciplinas. Custa uma consulta (`disciplinas_por_termo`, 609 ms para 18.634
termos), feita uma vez e guardada em cache.

Isto é o mesmo princípio do IDF — raridade como sinal — mas aplicado à
dimensão que interessa aqui: espalhamento por disciplina, não por documento.

Juntou-se ainda uma lista de **palavras funcionais inglesas** (`must`, `have`,
`your`, `with`...), porque o material de Inglês e os manuais de software estão
cheios delas.

## Estado final

| Disciplina | Temas |
|---|---|
| Matemática | variavel · geometria · amostra · dispersao · variabilidade · outliers · interquartil · desvio |
| Física-Química | radiacao · onda · comprimento · termodinamica · temperatura · espectro · calor |
| Português | amor · farsa · cantigas · vicente · trovadoresca · personagens |
| PSI | arrays · forms · studio · string · vetor · access · windows · visual |
| TIC | mode · edit · atalho · diapositivos · rato · paragrafo · submenu · menus |
| Área de Integração | ocidental · arte · seculo · contemporanea · esteticas · modernismo · epoca |
| Arq. Computadores | performance · reliability · nvidia · overclock · intel · ameacas |
| Educação Física | motoras · coordenativas · condicionais · ginastica · saudavel |
| Inglês | written · rules · presentations · speaking · english |

Resíduo honesto que fica: `crie` (imperativo — cobrir imperativos arriscaria
nomes como *base*, *classe*, *arte*, *fase*), `trab` e `point` (abreviaturas),
`indviduo` (gralha no documento original) e as abreviaturas de Horários, que
são o conteúdo real da tabela.

---

# Incidente: a chave de assinatura estava no índice

Ao investigar duas disciplinas estranhas ("data" com 1 documento e "livros"
com 480), descobriu-se que a indexação tinha corrido sobre `data/` em vez de
`data/raw/`. Consequências:

- `data/segredo.txt` — **a chave HMAC que assina as sessões** — foi indexada e
  tornou-se pesquisável.
- `data/livros/arquitetura-limpa.pdf` — o livro do corpus antigo — entrou como
  disciplina.

Correções:

1. **Chave regenerada.** Uma chave que entrou num índice pesquisável tem de
   ser tratada como comprometida. As sessões antigas ficaram inválidas — sem
   impacto, porque o beta ainda não começou.
2. **Guarda no ingestor.** `local_source` recusa agora, por nome e extensão,
   `segredo.txt`, `participantes.json`, `.env` e qualquer `.sqlite3`/`.db`/
   `.key`/`.pem` — **independentemente do caminho indicado**. Confiar em quem
   escreve o comando certo não é uma defesa.
3. **Reindexação** a partir de `data/raw`: 1.797 documentos, 12 disciplinas.


---

# Terceira ronda: mecanismos em vez de listas

Ruído que ainda passava: `aumenta`, `menor`, `vazio`, `percentagens`,
`return`, `conn`, `ficharevisoes`, `passagemde`.

## 1. camelCase no tokenizer (corrige indexação *e* temas)

`ficharevisoes` vinha do título `FichaRevisoes.pdf`. O tokenizer baixava a
caixa antes de olhar para as maiúsculas, colando tudo num só token.

```python
_PADRAO_CAMEL = re.compile(r"([a-z0-9])([A-Z])")
```

`FichaRevisoes` → `ficha revisoes`; `GestCampeonato` → `gest campeonato`;
`PowerPoint` → `power point`. Siglas (`PDF`, `HTML`, `PSI9`) ficam intactas,
porque não há transição minúscula→maiúscula.

Isto não é só cosmética de temas: **melhora a busca**. Quem pesquisar
"revisões" passa a encontrar o ficheiro `FichaRevisoes.pdf`.

## 2. Forma verbal detetada pelo próprio corpus

`aumenta` é verbo, mas termina em `-a`, e uma regra de sufixo para `-a`
apanharia metade dos nomes portugueses. A solução usa o vocabulário como
dicionário:

> `aumenta` é verbo **porque `aumentar` existe no índice**.

```python
def e_forma_verbal(termo, vocabulario):
    if len(termo) < 5 or termo[-1] not in "ae":
        return False
    return any(c in vocabulario for c in (termo + "r", termo[:-1] + "er", termo[:-1] + "ir"))
```

Testado contra o corpus real: apanha `aumenta`, `representa`, `utiliza`,
`permite`, `figura`, `forma`, `marca`. Deixa passar `onda`, `amostra`,
`temperatura`, `arte`, `farsa`, `cantiga`, `geometria`, `dispersao`, `obra` —
nomes que não têm infinitivo homógrafo.

## 3. Palavras-chave de código

`return`, `void`, `null`, `public`, `static`, `conn`, `query`... aparecem em
material de programação mas não são matéria. Lista dedicada — note-se que
`arrays`, `string` e `vetor` **ficam**, porque nessa disciplina são temas
legítimos.

## Uma regra que testei e rejeitei

Para `passagemde` (extração de PDF que perdeu o espaço em "passagem de"),
tentei detetar concatenações: se o token termina numa stop word e o prefixo
existe no vocabulário, é colagem.

Medido: apanharia **1.221 dos 18.182 termos**, incluindo particípios
legítimos (`abordada`, `acompanhado`, `adotada`) que terminam em `da`/`do` —
que são stop words. Risco de falsos positivos alto demais para remover um
token. **Rejeitada.**

Uma variante anterior (as duas metades existem no vocabulário) foi rejeitada
pelo mesmo motivo: marcava `termodinamica` como `termo`+`dinamica` e
`intencionalidade` como `intencional`+`idade`.

## Resíduo final, sem esconder

| Termo | Disciplina | Porquê fica |
|---|---|---|
| `crie` | PSI | imperativo; cobrir imperativos arriscaria *base*, *classe*, *arte*, *fase* |
| `passagemde`, `valore` | PSI | extração de PDF perdeu espaços/letras |
| `indviduo` | Área de Integração | gralha no documento original |
| `trab`, `capa`, `ctrl` | várias | abreviaturas reais do material |
| `port`, `comp`, `psic` | Horários | é literalmente o conteúdo da tabela |
| `sebenta` | Física-Química | tipo de documento, não tema — mas é como os alunos lhe chamam |

Não há aqui mais nada a ganhar sem um dicionário morfológico do português
(spaCy, ~500 MB) ou correção manual do corpus. O que existe é honesto:
cada regra foi medida, e as que falharam a medição foram deitadas fora.
