# Arquitetura de fontes

Documento de projeto. Define o que a Madalena passa a ser, de onde vem o
conteúdo, e como cada fonte se liga ao motor já construído.

## 1. O que a Madalena é

Um buscador vertical para os alunos da ESCO. Uma caixa de pesquisa sobre o
conteúdo que hoje está espalhado por site, Moodle, Teams e grupos de
WhatsApp.

**Princípio central: catálogo, não repositório.**
A Madalena sabe onde as coisas estão e mostra o suficiente para as
identificar. Não se substitui à fonte.

**Corolário: o índice encontra, a fonte manda.**
Uma cópia nossa pode estar desatualizada; o link para a origem é sempre a
verdade. Toda apresentação de resultado mostra a data e aponta para a fonte.

## 2. O contrato: Documento

Todas as fontes produzem a mesma estrutura. O motor (tokenizer, índice,
SQLite, busca, ranker) não sabe de onde o documento veio — foi para isto que
as camadas foram separadas na Etapa 1.

```
Documento
  id, titulo, texto, origem     ← já existe hoje
  url            onde a coisa vive (link profundo, com #page= quando PDF)
  fonte          local | site | moodle | teams
  tipo           ficha | trabalho | horario | comunicado | regulamento | outro
  disciplina     opcional — filtro
  ano_curso      opcional — filtro
  data           publicação/modificação — recência no ranking
  grupos         conjunto de códigos que podem ver este documento (ACL)
```

Os campos novos entram já, mesmo quando ainda não são usados: custam quase
nada agora e evitam migração de esquema depois.

## 3. As fontes

| Fonte | Como se lê | O que exige | Fase |
|---|---|---|---|
| **Pasta local** | `local_source.py` (já feito) | nada | 1 |
| **www.sefo.pt** | crawler HTTP: sitemap + robots.txt | nada (público) | 2 |
| **Moodle** | Web Services API + token de serviço | admin emite token | 3 |
| **Teams** | Microsoft Graph (ficheiros vivem em SharePoint) | registo de app + consentimento de admin | 3 |
| **Escola Virtual / manuais** | — | conteúdo licenciado: **só link, nunca cópia** | — |

Notas por fonte:

- **sefo.pt**: WordPress. `robots.txt` permissivo (bloqueia apenas
  `/wp-admin/` e uploads de formulários) e publica
  `https://www.sefo.pt/sitemap_index.xml` — a lista oficial de páginas. O
  crawler parte do sitemap em vez de seguir links às cegas.
- **Moodle**: a leitura é feita por um utilizador de serviço com token
  emitido pelo administrador, com âmbito nas disciplinas autorizadas. Nunca
  com credenciais de aluno, nunca automatizando o login de uma pessoa.
- **Teams**: os ficheiros publicados num canal aterram na biblioteca de
  documentos do SharePoint da equipa. Pedir `Sites.Selected` (o admin
  autoriza site a site, revogável) em vez de acesso global. Indexar
  **ficheiros e definições de trabalhos**; nunca conversas de canal (dados
  pessoais de menores, e permissões protegidas pela Microsoft).

## 4. Controlo de acesso: grupos

Numa escola, permissão é por **grupo**, não por pessoa. Ninguém publica
"visível ao João e à Maria"; publica numa disciplina de uma turma.

- Cada documento carrega os grupos que o podem ver: `{PSI-11B}`
- Cada aluno carrega os grupos a que pertence: `{PUBLICO, ESCOLA-TODOS,
  PSI-11B, ...}`
- O aluno vê o documento se os conjuntos se cruzarem

```
consulta → tokenizar
         → interseção das posting lists       (já feito)
         → FILTRO: grupos(doc) ∩ grupos(aluno) ≠ ∅   (novo)
         → ranquear TF-IDF                    (já feito)
```

O filtro entra **antes** do ranking: filtrar depois do corte do top-N faria
o aluno receber poucos resultados por os outros serem de outra turma.

Tabelas novas, no mesmo padrão muitos-para-muitos da `postings`:

```sql
grupos        (id, codigo)
doc_grupos    (doc_id, grupo_id)     -- ACL
aluno_grupos  (aluno_id, grupo_id)   -- matrículas
```

A ACL **cai da ingestão**: um ficheiro que veio da disciplina PSI-11B tem
ACL `{PSI-11B}`. Não há configuração manual de permissões.

**Propriedade elegante**: o utilizador não autenticado é o caso em que os
grupos são `{PUBLICO}`. Conteúdo público e conteúdo restrito usam o mesmo
código; muda o filtro, não o sistema.

**Cache de matrículas**: `aluno_grupos` é re-sincronizada no login (uma
chamada à API). Entre logins, confia-se no valor guardado.

## 5. Consequência de desenho: o login não é opcional

Mostrar sequer um excerto de uma ficha de PSI a quem não está identificado é
fuga de conteúdo entre turmas. Portanto:

| Fase | Conteúdo | Login |
|---|---|---|
| 1–2 | pasta local (pessoal) e sefo.pt (público) | não |
| 3 | Moodle e Teams | **sim, obrigatório**, com ACL |

No momento em que o Moodle entra, o SSO entra junto. O mesmo registo de
aplicação na Graph API serve para autenticação (conta Microsoft da escola) e
para o conector do Teams — o aluno entra com a conta que já usa.

O login não acrescenta fricção: substitui três (Moodle, Teams, Escola
Virtual) por um.

## 6. Piloto: PSI

Objetivo do piloto: validar se busca sobre material escolar resolve a dor
real, antes de pedir qualquer acesso institucional.

- **Corpus**: ficheiros das disciplinas de PSI, descarregados manualmente
  para `data/raw/psi/` (o Moodle oferece descarregar pasta em ZIP).
- **Ingestão**: `local_source.py`, já pronto. O "conector" desta fase é uma
  pessoa com um rato — e o motor não nota diferença.
- **Uso**: ferramenta local. Ao mostrar a colegas de PSI, nota-se que todos
  já têm o mesmo acesso ao conteúdo; ainda assim, avisar os professores que
  apoiam o projeto torna a coisa limpa.
- **Não fazer**: automatizar login com credenciais pessoais (violação típica
  de política de uso, credenciais no código, registos em nome do aluno), e
  republicar material de terceiros (digitalizações de manuais, Escola
  Virtual).

Com o piloto a funcionar, o pedido ao TI deixa de ser uma ideia e passa a
ser uma demonstração — o argumento que abre a Fase 3.

## 7. O que muda no motor

Nada da Etapa 1 à 6 é descartado. O que se acrescenta:

- campos novos no `Documento` e no esquema SQLite
- filtro de ACL entre a busca e o ranking
- recência no ranqueamento (um comunicado de hoje vale mais que um de 2019)
- filtros por tipo/disciplina/ano (busca facetada)
- interface responsiva: telemóvel no corredor, telão na sala
- reindexação incremental
