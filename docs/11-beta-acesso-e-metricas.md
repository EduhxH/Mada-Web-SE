# Beta fechado: acesso por código e métricas de utilização

Objetivo duplo: manter o projeto **confidencial** entre os participantes
escolhidos e recolher dados **rigorosos** para a apresentação.

## Porquê códigos individuais e não uma password partilhada

Uma password única fecharia o acesso, mas todos seriam a mesma pessoa aos
olhos do sistema. Com um código por participante:

- mede-se **quantos participantes distintos** usaram, e com que frequência
- vê-se quem voltou e quem não voltou (adesão real, não cliques)
- se um código circular fora do grupo, revoga-se **esse** e não o acesso todo

```
python main.py participantes --criar 8
python main.py participantes --revogar aluno-03 --criar 1
```

Alfabeto sem caracteres ambíguos (`O/0`, `I/1`), para ninguém falhar a
escrever.

## Os códigos não são guardados

O ficheiro `data/participantes.json` guarda apenas o **HMAC-SHA256** de cada
código:

```json
{ "6065af1a...277f211a": "aluno-01" }
```

Quem abrir o ficheiro não consegue entrar: o hash não se inverte. E por ser
HMAC (com chave) e não hash simples, nem força bruta sobre os 32^8 códigos
possíveis serve sem ter também `data/segredo.txt` — são precisos os dois.

Consequência: os códigos **só aparecem uma vez**, no momento da criação.
Perdeu-se um? Revoga-se esse participante e cria-se outro; os restantes não
são afetados.

Códigos antigos guardados em claro são migrados para hash automaticamente na
primeira leitura.

## O segredo de assinatura

Ordem de procura: variável de ambiente `MADALENA_SEGREDO` → ficheiro `.env` →
`data/segredo.txt` (gerado na primeira execução). Num alojamento a sério
injeta-se por variável de ambiente e não fica segredo nenhum em ficheiro.
Ver `.env.example`.

> Nota: um `.env` **não é mais seguro** que outro ficheiro — é texto simples
> no mesmo disco. O que protege os códigos é o hash; o `.env` serve para
> configuração de implantação.

## Como funciona a sessão

O código é trocado por um **cookie assinado**:

```
aluno-03|1756233600|a3f2b8c1...
└ rótulo ┘└ emitido ┘└ assinatura ┘
```

Mudar `aluno-03` para `aluno-99` invalida a assinatura. A comparação usa
`hmac.compare_digest`, que demora sempre o mesmo tempo — não deixa adivinhar
a assinatura byte a byte pelo tempo de resposta.

Validade 30 dias, cookie `HttpOnly` e `SameSite=Lax`.

Testado: cookie adulterado, chave errada, expirado e malformado são todos
recusados.

## O que está protegido

| Rota | Sem código |
|---|---|
| `/` e `/?q=...` | página de entrada — **verificado que não vaza resultados** |
| `/documento`, `/preview`, `/abrir`, `/estatisticas` | 403 |

## Métricas recolhidas

Base separada (`data/uso.sqlite3`) — reindexar não apaga o histórico.

| Evento | Quando | Guarda |
|---|---|---|
| `entrada` | login | participante |
| `busca` | cada pesquisa | consulta, disciplina, nº de resultados, modo (E/OU) |
| `abertura` | clique num resultado | doc_id, **posição** na lista |
| `preview` | hover/toque | doc_id |
| `sugestao_aceite` | clique em "será que quis dizer" | consulta corrigida |

### O problema dos cliques externos

Os PDFs do site apontam para `sefo.pt`. Com link direto, o navegador ia lá e
o servidor **nunca saberia** — a taxa de abertura ficaria falsamente baixa.
Solução: rota `/abrir?id=N`, que regista e responde `303` para a URL real.
É o mesmo mecanismo dos motores de busca comerciais.

## Métricas que importam para a apresentação

- **Taxa de consultas sem resultado** — mede se o motor falha aos alunos.
- **Taxa de abertura** — proporção de buscas que levaram a abrir um
  documento. É o indicador de *sucesso*, não de atividade.
- **Posição do clique** — se abrem quase sempre o 1.º resultado, o
  ranqueamento está bom.
- **Taxa de parciais (OU)** — quantas vezes o E falhou e foi preciso recorrer.
- **Consultas que falharam** — a lista mais útil de todas: diz exatamente o
  que falta indexar.

`/estatisticas` mostra tudo com gráficos em SVG gerado à mão — sem
bibliotecas, sem CDN, sem enviar dados para lado nenhum.

## Privacidade

- **Não** se guardam nomes, emails nem endereços IP.
- Cada participante é um rótulo (`aluno-01`); o mapa código→rótulo existe
  apenas como hash, e a correspondência real fica com o investigador.
- A página de entrada **diz explicitamente** o que é registado, antes de
  qualquer código ser introduzido — consentimento informado, boa prática de
  investigação e requisito do RGPD, ainda mais com menores.
- `.env`, `data/segredo.txt`, `data/participantes.json` e `data/uso.sqlite3`
  estão no `.gitignore`.

## Pôr no ar

```
python main.py web --host 0.0.0.0 --porta 8080
```

Avisa no arranque que aceita ligações externas. Em HTTP simples o código
viaja em claro na rede local — para acesso pela internet, usar um túnel com
HTTPS (Cloudflare Tunnel ou equivalente).
