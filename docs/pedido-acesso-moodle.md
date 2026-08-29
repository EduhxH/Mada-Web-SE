# Pedido de acesso de leitura ao Moodle (Web Services)

**Para:** Administração do Moodle / Serviços de Informática — ESCO
**De:** Eduardo Carvalho, turma PSI9
**Assunto:** Token de leitura para projeto escolar de motor de busca

---

## O que é o projeto

Desenvolvi um motor de busca que reúne, numa única caixa de pesquisa, os
materiais que hoje estão espalhados pelo site da escola, pelo Moodle e por
grupos de WhatsApp. O objetivo é reduzir o tempo que os alunos perdem à
procura de fichas, horários e regulamentos.

O sistema já está **a funcionar**: indexa neste momento 1.797 documentos —
1.010 páginas e PDFs do site público da escola (respeitando o `robots.txt` e
com limite de velocidade) e 787 documentos de 11 disciplinas.

O projeto está a ser desenvolvido no âmbito escolar, com o apoio de
professores da turma, e destina-se a um teste piloto com um pequeno grupo de
alunos de PSI9.

## O que peço

Acesso de **leitura** através dos Web Services do Moodle:

1. Ativação dos Web Services (protocolo REST)
2. Um **utilizador de serviço** com um papel de apenas-leitura
3. Um **token** para esse utilizador, limitado a **2 ou 3 disciplinas** de
   PSI9, durante um período experimental

Não peço acesso à minha conta de aluno nem a credenciais de terceiros.

## O que o sistema faz com o acesso

Lê a lista de materiais publicados pelos professores nessas disciplinas
(fichas, sebentas, enunciados) e constrói um índice de pesquisa.

## O que o sistema **não** faz

- **Não republica conteúdo.** Os resultados apontam para o documento no
  Moodle. O sistema é um catálogo, não um repositório.
- **Não acede a dados pessoais.** Pautas, notas, listas de alunos e contactos
  são excluídos automaticamente. Ficheiros cujo nome contenha "notas",
  "pauta" ou "classificações" são recusados pelo próprio código, e isso é
  verificado por testes automáticos.
- **Não escreve nada.** Não publica, não altera, não apaga.
- **Não contorna permissões.** Cada aluno só vê o material das disciplinas em
  que está inscrito, exatamente como no Moodle.
- **Não usa credenciais de alunos.** Nenhum login é automatizado.

## Garantias técnicas

- O sistema corre numa máquina local, sem serviços de terceiros a alojar
  dados da escola.
- O acesso está fechado por códigos individuais; não é público.
- Os dados de utilização são pseudonimizados: cada participante é um rótulo
  (`aluno-01`), sem nomes, sem emails, sem endereços IP.
- Todo o código está disponível para revisão.
- **O token é revogável a qualquer momento**, e o acesso termina de imediato.

## Alternativa, se preferirem

Se o token não for possível, o projeto continua a funcionar — o material é
descarregado manualmente. O pedido é apenas para que a atualização deixe de
depender de trabalho manual e o índice não fique desatualizado.

## Disponibilidade

Posso demonstrar o sistema a funcionar, mostrar o código, ou ajustar o âmbito
do acesso ao que for considerado adequado.

---

**Contacto:** Eduardo Carvalho, PSI9
