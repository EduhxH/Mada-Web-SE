"""Folha de estilo do painel de administracao.

Fica num modulo seu e nao dentro de `estilo.py` por uma razao de peso literal:
so o administrador ve estas paginas. Juntar quatro kilobytes de estilos de
tabela, consola e editor ao CSS comum era manda-los em cada busca de cada aluno,
para nada - e o CSS vai em linha no HTML, portanto nem o cache do browser o
salvava.

O painel obedece as mesmas tres regras do resto da interface: cantos a zero,
tres familias com papeis separados, monocromatico. Ha duas excecoes pensadas, e
ambas existem porque a alternativa nao funcionava:

**No registo, um erro leva o preto e o branco trocados.** Sem cor de realce, a
unica forma de uma linha saltar a vista num ecra de texto cinzento e inverter-se.
Um registo onde o erro nao salta a vista nao serve para aquilo que foi feito.

**Os botoes destrutivos sao tracejados, nao vermelhos.** Revogar um acesso e
apagar um post tem de se ler como "isto nao e um botao normal" - e o traco
interrompido diz isso sem introduzir uma cor que a paleta nao tem.
"""

CSS = """
.pn { margin: 0 auto; max-width: 1440px; padding: 0 32px 64px; }
.pn-grelha {
  display: grid; grid-template-columns: 232px minmax(0, 1fr);
  gap: 48px; padding-top: 40px; align-items: start;
}

/* ---------- navegacao lateral ---------- */

.pn-nav { position: sticky; top: 96px; }
.pn-nav .olho { margin-bottom: 14px; }
.pn-nav a {
  display: flex; align-items: center; gap: 11px;
  padding: 10px 12px; margin-left: -12px;
  font-size: 13px; color: var(--texto-3); text-decoration: none;
  border: 1px solid transparent;
  transition: color .2s var(--curva), background-color .2s var(--curva);
}
.pn-nav a:hover { color: var(--texto); background: var(--suave); }
.pn-nav a.ativa {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}
.pn-nav a .rotulo { flex: 1; min-width: 0; }
.pn-ponto {
  flex: none; min-width: 18px; height: 18px; padding: 0 5px;
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 10px; line-height: 1;
  border: 1px solid var(--linha-forte); color: var(--texto-2);
}
.pn-nav a.ativa .pn-ponto {
  border-color: var(--sobre-solido); color: var(--sobre-solido);
}

/* ---------- cabeca e cartoes ---------- */

.pn-cabeca { border-bottom: 1px solid var(--linha); padding-bottom: 22px; }
.pn-cabeca h1 { margin: 10px 0 0; font-size: clamp(1.8rem, 3.4vw, 2.6rem); }
.pn-cabeca .lead {
  margin: 12px 0 0; max-width: 62ch; font-size: 14px; color: var(--texto-3);
}
.pn-secao { margin-top: 44px; }
.pn-secao > .olho { margin-bottom: 16px; }
.pn-linha-titulo {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 16px; flex-wrap: wrap; margin-bottom: 16px;
}
.pn-linha-titulo .olho { margin: 0; }
.pn-cartao { border: 1px solid var(--linha); padding: 20px; }
.pn-nota { margin: 14px 0 0; font-size: 12px; line-height: 1.7; color: var(--texto-4); }
.pn-nota strong { color: var(--texto-2); font-weight: 600; }
.pn-vazio { padding: 40px 0; font-size: 14px; color: var(--texto-4); }
.pn-recado {
  margin: 20px 0 0; padding: 13px 16px;
  border: 1px solid var(--linha-forte); font-size: 13px; color: var(--texto-2);
  display: flex; align-items: flex-start; gap: 10px;
}
.pn-recado.mau { background: var(--solido); color: var(--sobre-solido); border-color: var(--solido); }
.pn-recado code {
  font-family: var(--mono); font-size: 13px; letter-spacing: .1em;
  background: var(--suave); padding: 1px 6px; color: var(--texto);
}

/* ---------- botoes do painel ---------- */

.pn-botao {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  height: 36px; padding: 0 13px;
  font-family: inherit; font-size: 12px; color: var(--texto-2);
  background: none; border: 1px solid var(--linha-forte);
  cursor: pointer; text-decoration: none; white-space: nowrap;
  transition: color .2s var(--curva), border-color .2s var(--curva),
              background-color .2s var(--curva);
}
.pn-botao:hover:not(:disabled) { color: var(--texto); border-color: var(--texto); }
.pn-botao:disabled { opacity: .4; cursor: not-allowed; }
.pn-botao.forte {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
  font-weight: 600;
}
.pn-botao.forte:hover:not(:disabled) { opacity: .82; color: var(--sobre-solido); }
.pn-botao.perigo { border-style: dashed; }
.pn-botao.perigo:hover:not(:disabled) { border-style: solid; }
.pn-acoes { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.pn-acoes form { display: inline-flex; }

/* ---------- tabela de utilizadores ---------- */

.pn-rolo { overflow-x: auto; }
.pn-tabela { width: 100%; border-collapse: collapse; font-size: 13px; }
.pn-tabela th {
  text-align: left; padding: 0 12px 10px 0;
  font-family: var(--mono); font-size: 10px; font-weight: 400;
  text-transform: uppercase; letter-spacing: .14em; color: var(--texto-4);
  border-bottom: 1px solid var(--linha); white-space: nowrap;
}
.pn-tabela td {
  padding: 14px 12px 14px 0; border-bottom: 1px solid var(--linha);
  vertical-align: middle;
}
.pn-tabela tr:hover td { background: var(--suave); }
.pn-tabela td.acoes-celula { width: 1%; white-space: nowrap; }
.pn-rotulo { font-family: var(--mono); font-size: 12px; color: var(--texto); }
.pn-papel {
  font-family: var(--mono); font-size: 9px; text-transform: uppercase;
  letter-spacing: .12em; color: var(--texto-3);
  border: 1px solid var(--linha); padding: 2px 6px; margin-left: 8px;
}
.pn-quem { display: flex; align-items: center; gap: 10px; }
.pn-estado { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
/* O ponto cheio e quem esta; o vazio e quem nao esta. Duas formas, nao duas
   cores - numa interface a preto e branco a cor nao esta disponivel. */
.pn-bolha {
  width: 8px; height: 8px; border-radius: 50%; flex: none;
  border: 1px solid var(--texto-3);
}
.pn-bolha.online { background: var(--texto); border-color: var(--texto); }
.pn-faz {
  color: var(--texto-3); display: block; max-width: 28ch;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pn-aparelho { display: inline-flex; align-items: center; gap: 7px; color: var(--texto-3); }

/* ---------- consola de registo ---------- */

.pn-consola {
  margin-top: 4px; height: min(62vh, 620px); overflow-y: auto;
  border: 1px solid var(--linha); background: var(--cartao);
  font-family: var(--mono); font-size: 12px; line-height: 1.65;
}
.pn-consola .ln {
  display: grid; grid-template-columns: 64px 58px minmax(0, 1fr);
  gap: 12px; padding: 4px 14px; border-bottom: 1px solid var(--linha);
}
.pn-consola .ln:last-child { border-bottom: none; }
.pn-consola .hora { color: var(--texto-4); }
.pn-consola .nivel {
  font-size: 10px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--texto-4); overflow: hidden; text-overflow: ellipsis;
}
.pn-consola .texto { white-space: pre-wrap; word-break: break-word; color: var(--texto-2); }
.pn-consola .ln.aviso { border-left: 2px solid var(--linha-forte); }
.pn-consola .ln.aviso .nivel, .pn-consola .ln.aviso .texto { color: var(--texto); }
.pn-consola .ln.erro { background: var(--solido); }
.pn-consola .ln.erro .hora,
.pn-consola .ln.erro .nivel,
.pn-consola .ln.erro .texto { color: var(--sobre-solido); }
.pn-consola .ln.erro .nivel { font-weight: 500; }
/* O filtro "so avisos e erros" e uma classe no contentor e nao um pedido novo:
   as linhas informativas ja estao na pagina, e esconde-las e instantaneo. */
.pn-consola.so-graves .ln.info { display: none; }
.pn-barra-consola {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 12px;
}
.pn-barra-consola label {
  display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--texto-3);
}
.pn-viva {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}
.pn-viva .bat { width: 6px; height: 6px; border-radius: 50%; background: var(--texto-3); }
.pn-viva.ligada .bat { background: var(--texto); animation: pulsar 2s infinite; }
@keyframes pulsar { 0%, 100% { opacity: 1; } 50% { opacity: .25; } }

/* ---------- automatizacao ---------- */

.pn-operacoes {
  display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
}
.pn-op h3 { margin: 0; font-size: 15px; font-weight: 600; }
.pn-op .quando { margin: 8px 0 0; font-size: 12px; color: var(--texto-4); }
.pn-op .resultado { margin: 10px 0 0; font-size: 13px; color: var(--texto-2); }
.pn-op .pn-acoes { margin-top: 16px; }
.pn-selo {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .12em; border: 1px solid var(--linha-forte); padding: 2px 7px;
}
.pn-selo.mau {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}

/* ---------- newsletter no painel ---------- */

.pn-editor { display: grid; gap: 24px; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.pn-campo { display: block; margin-bottom: 16px; }
.pn-campo > span {
  display: block; margin-bottom: 7px;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}
.pn-campo input[type=text], .pn-campo textarea, .pn-campo input[type=file] {
  width: 100%; font-family: inherit; font-size: 14px;
  color: var(--texto); background: transparent;
  border: 1px solid var(--linha-forte); border-radius: 0;
  padding: 11px 13px; outline: none;
  transition: border-color .2s var(--curva);
}
.pn-campo input[type=text]:focus, .pn-campo textarea:focus { border-color: var(--texto); }
.pn-campo textarea {
  min-height: 430px; resize: vertical;
  font-family: var(--mono); font-size: 13px; line-height: 1.7;
}
.pn-campo input[type=file] { font-family: var(--mono); font-size: 12px; padding: 9px 11px; }
.pn-ferramentas { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.pn-ferramentas button {
  height: 30px; min-width: 32px; padding: 0 9px;
  font-family: var(--mono); font-size: 11px; color: var(--texto-3);
  background: none; border: 1px solid var(--linha); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.pn-ferramentas button:hover { color: var(--texto); border-color: var(--texto-3); }
.pn-previa { border: 1px solid var(--linha); padding: 20px; max-height: 640px; overflow-y: auto; }
.pn-previa .nl-corpo { margin-top: 0; }
.pn-lista-posts { list-style: none; margin: 0; padding: 0; }
.pn-lista-posts li {
  display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;
  border-bottom: 1px solid var(--linha); padding: 16px 0;
}
.pn-lista-posts .principal { flex: 1; min-width: 240px; }
.pn-lista-posts h3 { margin: 0; font-size: 15px; font-weight: 600; }
.pn-lista-posts h3 a { text-decoration: none; }
.pn-lista-posts h3 a:hover { text-decoration: underline; text-underline-offset: 3px; }
.pn-lista-posts .resumo { margin: 6px 0 0; font-size: 13px; color: var(--texto-3); }
.pn-lista-posts .meta {
  margin: 8px 0 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .12em; color: var(--texto-4);
}

/* ---------- biblioteca de media ---------- */

.pn-media { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr)); }
.pn-media figure { margin: 0; border: 1px solid var(--linha); }
.pn-media img, .pn-media video {
  display: block; width: 100%; height: 108px; object-fit: cover; background: var(--suave);
}
.pn-media figcaption {
  padding: 8px 10px; font-family: var(--mono); font-size: 10px; color: var(--texto-4);
  display: flex; flex-direction: column; gap: 6px;
}
.pn-media .cod {
  width: 100%; font-family: var(--mono); font-size: 10px; padding: 4px 6px;
  color: var(--texto-2); background: transparent; border: 1px solid var(--linha);
}

/* ---------- perfil ---------- */

.pn-perfil { display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap; }
.pn-retrato-grande {
  width: 132px; height: 132px; object-fit: cover; flex: none;
  border: 1px solid var(--linha-forte); background: var(--suave);
}
.pn-retrato-vazio {
  width: 132px; height: 132px; flex: none; display: grid; place-items: center;
  border: 1px dashed var(--linha-forte); color: var(--texto-4);
}
.pn-perfil .lado-forma { flex: 1; min-width: 260px; }

/* ---------- tablet ---------- */

@media (max-width: 1080px) {
  /* `minmax(0, 1fr)` e nao `1fr`: uma coluna `1fr` tem `min-width: auto`, o que
     a impede de encolher abaixo do seu conteudo. A tira de navegacao tem seis
     itens e mede 753px; em vez de deslizar dentro do seu `overflow-x`, esticava
     a coluna e a pagina inteira passava a ter 771px de largura num ecra de 375.
     Medido com `scrollWidth` no telemovel emulado - de olho nao se via, porque o
     que transbordava era o menu e nao o texto. */
  .pn-grelha { grid-template-columns: minmax(0, 1fr); gap: 28px; }
  .pn-nav { position: static; min-width: 0; }
  /* Em coluna estreita o menu deixa de ser lista e passa a tira deslizante: seis
     itens em vertical empurravam o conteudo do painel para fora do primeiro
     ecra, e a primeira coisa que se quer ver e o conteudo. */
  .pn-nav .pn-itens {
    display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px;
    scrollbar-width: none;
  }
  .pn-nav .pn-itens::-webkit-scrollbar { display: none; }
  .pn-nav a { margin-left: 0; border-color: var(--linha); white-space: nowrap; }
  .pn-nav .olho { display: none; }
  .pn-editor { grid-template-columns: 1fr; }
  .pn-previa { max-height: 320px; }
}

/* ---------- telemovel ---------- */

@media (max-width: 820px) {
  .pn { padding: 0 18px 48px; }
  .pn-grelha { padding-top: 24px; }
  .pn-campo textarea { min-height: 300px; }
  .pn-consola { height: 52vh; font-size: 11px; }
  .pn-consola .ln { grid-template-columns: 54px 46px minmax(0, 1fr); gap: 8px; padding: 4px 10px; }
  /* A tabela de oito colunas nao cabe em 375px de nenhuma maneira: cada linha
     passa a cartao, com os rotulos que a cabeca dava agora dentro das celulas. */
  .pn-tabela thead { display: none; }
  .pn-tabela tr { display: block; border-bottom: 1px solid var(--linha); padding: 14px 0; }
  .pn-tabela td { display: block; border: none; padding: 3px 0; }
  .pn-tabela td.acoes-celula { width: auto; white-space: normal; padding-top: 12px; }
  .pn-tabela tr:hover td { background: none; }
  .pn-faz { max-width: none; white-space: normal; }
}

/* ---------- telao da sala ---------- */

@media (min-width: 1600px) {
  .pn-grelha { grid-template-columns: 260px minmax(0, 1fr); }
  .pn-consola { font-size: 13px; }
  .pn-tabela { font-size: 15px; }
}
"""
