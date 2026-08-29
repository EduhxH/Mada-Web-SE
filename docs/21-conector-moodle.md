# Conector do Moodle

Sincroniza os materiais das disciplinas em que o utilizador está inscrito,
usando as suas próprias credenciais numa sessão autenticada.

## Configuração

Ficheiro `.env` na raiz do projeto (já está no `.gitignore`, nunca é
versionado):

```
MOODLE_URL=https://moodle.sefo.pt
MOODLE_UTILIZADOR=o_seu_utilizador
MOODLE_SENHA=a_sua_senha
```

A senha nunca aparece no código, em logs, ou em mensagens de erro.

## Uso

```bash
# ver o que existe, sem descarregar nada
python main.py moodle --listar

# experimentar com pouco: 3 recursos de uma disciplina
python main.py moodle --disciplina Matemática --limite 3

# sincronizar tudo
python main.py moodle

# depois, indexar
python main.py atualizar --sem-rastreio
```

Opções: `--disciplina` (repetível, filtra por nome), `--intervalo` (segundos
entre pedidos, por omissão 1), `--limite`, `--listar`.

## Como funciona

1. **Login pelo formulário do Moodle**, incluindo o `logintoken` anti-CSRF
   que ele exige — é o mesmo caminho de um navegador.
2. **Lista das disciplinas inscritas** a partir de `/my/courses.php`.
3. **Recursos de cada disciplina**: a página do curso é lida e extraem-se as
   ligações `/mod/<tipo>/view.php?id=N`.
4. **Descarregamento**: pastas usam `download_folder.php` (ZIP), recursos
   individuais usam `view.php?...&redirect=1`.
5. **Manifesto** `_origens.json` com o URL original de cada ficheiro, para
   os resultados ligarem de volta ao Moodle.

## Decisões

**Só material, não conversas.** `MODULOS_UTEIS` inclui `resource`, `folder`,
`page`, `book`, `url`. Ficam de fora fóruns, questionários, chats e
submissões de trabalhos — são conversas e avaliações, não material de estudo,
e contêm dados pessoais.

**Intervalo entre pedidos.** Um segundo por omissão. O servidor da escola não
deve notar diferença face a um aluno a navegar.

**Só leitura.** Nada é publicado, alterado ou apagado.

**Filtro de extensões.** Só formatos de documento. Imagens, vídeos e
executáveis são recusados.

## Um bug apanhado pelos testes

`_nome_da_resposta()` usava o nome do URL quando não havia
`Content-Disposition`. Mas um recurso que não redireciona fica em
`.../mod/resource/view.php`, cuja "extensão" é `.php` — e o ficheiro seria
guardado como `view.php`.

Corrigido: o nome do URL só é aceite se a extensão for de conteúdo real.

## Estado

Escrito e testado ao nível das funções (8 testes), mas **ainda não corrido
contra o Moodle real**. A primeira execução vai revelar diferenças da
instalação concreta — o HTML das páginas de curso varia entre versões e
temas. Começar com `--listar` e depois `--limite 3`.
