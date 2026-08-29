# Atualização do corpus num comando

```
python main.py atualizar
```

Rastreia o site da escola, reindexa tudo (site + material do Moodle) e diz
**o que mudou**.

```
1/2  A rastrear https://www.sefo.pt (max 400 paginas)...
     259 guardadas (139 HTML + 120 PDF) em 287 pedidos
2/2  A reindexar o corpus completo...
     1799 documentos, 18138 termos unicos

Concluido em 412s.  2 novos, 1 alterados, 1 removidos, 1795 inalterados

Novos (2):
  Criterios Avaliacao TIC 2026
  ficha-derivadas-set

Removidos (1):
  Circular no3 2024 2025
```

Opções: `--sem-rastreio` (só reindexa o que já está em disco), `--paginas`,
`--intervalo`, `--url`.

## Duas correções que isto obrigou a fazer

### Rastreio destrutivo → troca atómica

O rastreio escrevia por cima da pasta existente. Dois problemas:

- Uma página apagada do site **ficava indexada para sempre** — o ficheiro
  antigo continuava lá.
- Um rastreio interrompido a meio (rede a falhar, Ctrl+C) deixava o corpus
  meio escrito.

Agora escreve-se para `Escola.novo/` e só no fim, **se algo foi guardado**, se
troca pela pasta antiga. Falha a meio? A versão anterior fica intacta.

### O relatório de alterações só é possível por causa dos ids estáveis

Comparar duas indexações exige saber que "este documento" é o mesmo de antes.
Com ids sequenciais isso era impossível — acrescentar um ficheiro deslocava
todos os outros e tudo parecia ter mudado.

Como o id vem agora da origem (`docs/18`), a comparação é trivial:

| Situação | Deteção |
|---|---|
| id novo | documento **novo** |
| id desapareceu | documento **removido** |
| id igual, tamanho do texto diferente | documento **alterado** |
| id e tamanho iguais | **inalterado** |

Nota honesta: mover um ficheiro de disciplina conta como removido + novo,
porque a origem faz parte do id. É a interpretação certa — passou a ser
outro documento no catálogo.

## O que continua manual

O **Moodle**. Sem token de Web Services não há forma legítima de automatizar,
e a linha mantém-se: nunca automatizar login com credenciais de aluno. O
material continua a ser descarregado à mão para `data/raw/psi9/<Disciplina>/`
e depois o `atualizar` trata do resto.

Quando houver token, o conector Moodle encaixa como mais um passo do mesmo
comando — o `Documento` é o contrato e nada a jusante muda.

## Agendar (Windows)

Para correr sozinho todas as segundas às 8h, no Agendador de Tarefas:

- Programa: `D:\...\MadalenaWebSearchEngine\.venv\Scripts\python.exe`
- Argumentos: `main.py atualizar`
- Iniciar em: `D:\...\MadalenaWebSearchEngine`

O comando é seguro para correr repetidamente: reindexar duas vezes seguidas
não muda nada e os ids não se movem.
