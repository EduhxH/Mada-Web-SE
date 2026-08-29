# Conector do Moodle: sete bugs até funcionar

Estado final: **751 documentos** sincronizados automaticamente das 12
disciplinas, contra 787 do descarregamento manual de agosto — equivalente, e
sem trabalho manual nenhum.

O caminho até lá vale mais do que o resultado, porque cada falha ensinou algo
sobre depurar contra um sistema que não controlamos.

## Os bugs, por ordem de descoberta

### 1. `FileNotFoundError` em nomes de pasta

O Moodle trunca os nomes na lista de disciplinas
(`PSI9-Arquitetura de Computa...`) e o **Windows recusa pastas terminadas em
ponto**. O nome completo passou a vir do `<h1>` da página da disciplina.

### 2. Disciplinas duplicadas

O `<h1>` diz `Disciplina: PSI9-Nome`. A limpeza de prefixos só corria uma vez
e sobrava `Disciplina- PSI9-Nome`, criando uma segunda pasta por disciplina.
Agora repete até estabilizar.

### 3. 746 documentos chamados `view.php`

Para ficheiros dentro de ZIPs, a origem é `<url-do-zip>!<ficheiro>`. O título
vinha de `titulo_de_url()`, que analisava o URL, encontrava `view.php` no
caminho e ignorava o nome real. O URL só serve de título quando o documento
**é** esse URL.

### 4. O mesmo recurso em 12 disciplinas

As ligações eram extraídas da página inteira, incluindo blocos laterais. Um
anúncio partilhado aparecia em todas as disciplinas. Agora só se lê a região
de conteúdo (`#region-main`).

### 5. 233 pastas a falhar

`download_folder.php` é servido por **POST com sesskey** — um GET nunca ia
funcionar. Abandonado: abre-se a página da pasta e segue-se cada ficheiro
individualmente. Dá também nomes melhores que um ZIP anónimo.

### 6. 630 documentos repetidos

Ao acrescentar o `sesskey` ao URL, o hash do nome do ficheiro mudou entre
execuções e o mesmo conteúdo ficou guardado duas vezes. A chave do nome passou
a ser `módulo + id + ficheiro`, sem parâmetros voláteis.

### 7. 101 documentos repetidos (outro)

Todos os ficheiros de uma pasta ficavam com **o URL da pasta** como origem. O
id deriva da origem, portanto colidiam e só o primeiro ficheiro de cada pasta
sobrevivia. A origem passou a incluir o nome do ficheiro.

## O diagnóstico que parou as adivinhas

Depois de duas execuções de sete minutos a tentar perceber porque falhavam as
pastas, construí `main.py moodle --diagnostico`: abre várias pastas reais e
reporta o que cada página contém — estado, redirecionamentos, contagens de
`pluginfile.php`, `folder_tree`, `fp-filename`, e as primeiras ligações.

Respondeu em segundos:

```
Critérios de avaliação   fp-filename vazios: 1 | com nome: 1 | extraidos: 1
Manuais adotados         fp-filename vazios: 1 | com nome: 0 | extraidos: 0
```

O extrator funcionava. As pastas é que estavam **genuinamente vazias** — as
duas ocorrências de `pluginfile.php` nessas páginas eram o favicon e o
logótipo do tema. Confirmado depois no navegador.

Lição: quando cada tentativa custa sete minutos, construir a ferramenta de
observação compensa à primeira.

E o relatório passou a contar pastas vazias à parte, porque apresentar 233
delas como "Ignorados" fazia uma sincronização correta parecer avariada.

## O que fica de fora, de propósito

- **Fóruns, questionários, submissões** — conversas e avaliações, com dados
  pessoais de colegas.
- **Ficheiros `.xlsx`** — no corpus real são pautas de avaliação.
- **Módulo `url`** — aponta para sites externos, que não são conteúdo da
  escola.
- **Imagens** — sem OCR, não há texto para indexar.

## Uso

```
python main.py moodle --listar          # ver as disciplinas inscritas
python main.py moodle --diagnostico     # inspecionar a estrutura das pastas
python main.py moodle                   # sincronizar tudo
python main.py atualizar --sem-rastreio # indexar
```
