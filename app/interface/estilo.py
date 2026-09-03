"""Folha de estilo e esqueleto das paginas.

Vive fora de `web.py` porque sao duas coisas de natureza diferente: aqui e
aparencia, la e o que o servidor faz.

O desenho e o que o Eduardo planeou no Figma. Tres tracos mandam nele:

1. **Cantos a zero.** Nao ha um unico raio de borda em toda a interface. E o
   que lhe da o ar de publicacao em vez de aplicacao.
2. **Tres familias com papeis separados.** Libre Bodoni (serifada) so nos
   titulos grandes; DM Mono, maiuscula e muito espacejada, nas etiquetas
   pequenas; Manrope em todo o resto. O contraste entre a serifada enorme e a
   monoespacada minuscula e o que faz a pagina ter voz.
3. **Monocromatico.** Nenhuma cor de realce. O botao principal e o preto e o
   branco trocados; a separacao faz-se por linha de 1px e por espaco.

As fontes estao em `assets/fontes/` e sao servidas pela propria maquina - o
CSS do Figma ia busca-las ao Google, e a regra do projeto e nao depender de
servidores alheios. Manrope e Libre Bodoni sao variaveis: um ficheiro serve
todos os pesos, e por isso ha quatro ficheiros e nao oito.
"""

from app.interface import icones, som

# `swap` para o texto aparecer logo na fonte do sistema e trocar quando a
# verdadeira chegar. `display: block` deixava a pagina muda ate ao fim do
# descarregamento, o que na rede da escola se nota.
FONTES = """
@font-face {
  font-family: "Manrope"; font-style: normal; font-weight: 200 800;
  font-display: swap; src: url("/estatico/manrope.woff2") format("woff2");
}
@font-face {
  font-family: "Libre Bodoni"; font-style: normal; font-weight: 400 700;
  font-display: swap; src: url("/estatico/libre-bodoni.woff2") format("woff2");
}
@font-face {
  font-family: "DM Mono"; font-style: normal; font-weight: 400;
  font-display: swap; src: url("/estatico/dm-mono-400.woff2") format("woff2");
}
@font-face {
  font-family: "DM Mono"; font-style: normal; font-weight: 500;
  font-display: swap; src: url("/estatico/dm-mono-500.woff2") format("woff2");
}
"""

CSS = FONTES + """
:root {
  color-scheme: dark;
  --fundo: #0a0a0a;
  --texto: #f5f5f5;
  --cartao: #101010;
  --suave: #171717;
  --texto-2: #a1a1aa;
  --texto-3: #71717a;
  --texto-4: #52525b;
  --linha: #252525;
  --linha-forte: #3f3f46;
  --solido: #f5f5f5;
  --sobre-solido: #0a0a0a;
  --topo-fundo: rgba(10, 10, 10, .94);
  --gato-opacidade: .07;
  --gato-inverter: 1;

  --sans: "Manrope", -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  --display: "Libre Bodoni", Georgia, "Times New Roman", serif;
  --mono: "DM Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
  --curva: cubic-bezier(.4, 0, .2, 1);
}
@media (prefers-color-scheme: light) {
  :root:not([data-tema="escuro"]) {
    color-scheme: light;
    --fundo: #f7f7f5;
    --texto: #111111;
    --cartao: #ffffff;
    --suave: #ececea;
    --texto-2: #5f5f5b;
    --texto-3: #77776f;
    --texto-4: #9a9a92;
    --linha: #d8d8d4;
    --linha-forte: #a9a9a4;
    --solido: #111111;
    --sobre-solido: #ffffff;
    --topo-fundo: rgba(247, 247, 245, .94);
    --gato-opacidade: .07;
    --gato-inverter: 0;
  }
}
:root[data-tema="claro"] {
  color-scheme: light;
  --fundo: #f7f7f5;
  --texto: #111111;
  --cartao: #ffffff;
  --suave: #ececea;
  --texto-2: #5f5f5b;
  --texto-3: #77776f;
  --texto-4: #9a9a92;
  --linha: #d8d8d4;
  --linha-forte: #a9a9a4;
  --solido: #111111;
  --sobre-solido: #ffffff;
  --topo-fundo: rgba(247, 247, 245, .94);
  --gato-opacidade: .05;
  --gato-inverter: 0;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; min-height: 100%; }
body {
  background: var(--fundo);
  color: var(--texto);
  font-family: var(--sans);
  font-size: 15px; line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}
a { color: inherit; }
img { max-width: 100%; }
button, input, select { font: inherit; }
::selection { background: var(--texto); color: var(--fundo); }
.ic { flex: none; vertical-align: middle; }

/* Quem prefere menos movimento nao leva nenhum. Vale para o CSS, e o guiao
   das animacoes le a mesma preferencia. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .001ms !important;
    transition-duration: .001ms !important;
  }
}

/* Foco visivel sempre - a interface e toda a preto e branco e sem isto quem
   navega por teclado perde-se. */
:focus-visible { outline: 2px solid var(--texto); outline-offset: 3px; }

/* ---------- pecas de tipografia ---------- */

.olho {
  font-family: var(--mono); font-size: 10px; font-weight: 400;
  text-transform: uppercase; letter-spacing: .2em; color: var(--texto-4);
  margin: 0;
}
/* A entrelinha de .88 que veio do Figma foi desenhada para uma grotesca. O
   Libre Bodoni e um Bodoni e tem extensores longos; medido no proprio
   ficheiro, com `measureText`:

       q  desce 0.32em abaixo da linha de base
       b  sobe   0.76em acima
       i com acento sobe 0.77em

   Ou seja, as linhas **tocam-se** a partir de 1.09 (0.32 + 0.77) e qualquer
   valor abaixo disso e sobreposicao garantida, nao margem apertada. Foi o que
   aconteceu com 1.06: o "q" de "que" batia no "b" de "sabe", e o acento de
   "indice" batia na linha de cima.

   1.18 deixa 0.09em de folga. Em portugues isto nao e luxo - a lingua enche
   as linhas de acentos, que sobem tanto como as maiusculas. */
.display {
  font-family: var(--display); font-weight: 400;
  line-height: 1.18; letter-spacing: -.025em; color: var(--texto);
  margin: 0;
  word-spacing: .04em;
}
.h-gigante { font-size: clamp(2.5rem, 6.2vw, 5.6rem); }
.h-grande  { font-size: clamp(2.1rem, 4.6vw, 3.4rem); letter-spacing: -.02em; }

/* ---------- topo ---------- */

.topo {
  position: sticky; top: 0; z-index: 30;
  background: var(--topo-fundo);
  backdrop-filter: saturate(180%) blur(12px);
  -webkit-backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--linha);
}
.topo-linha {
  margin: 0 auto; max-width: 1440px;
  display: flex; align-items: center; gap: 24px;
  min-height: 72px; padding: 12px 32px;
}
.marca { display: flex; align-items: center; gap: 9px; text-decoration: none; flex: none; }
.marca img.gato { height: 30px; width: auto; }
.marca img.nome { height: 14px; width: auto; }

/* O desenho e tinta escura. Em fundo escuro inverte-se, em vez de guardar um
   segundo ficheiro que depois fica por atualizar. */
:root:not([data-tema="claro"]) .marca img,
:root:not([data-tema="claro"]) .marca-grande img { filter: invert(1); }
@media (prefers-color-scheme: light) {
  :root:not([data-tema="escuro"]) .marca img,
  :root:not([data-tema="escuro"]) .marca-grande img { filter: none; }
}
:root[data-tema="escuro"] .marca img,
:root[data-tema="escuro"] .marca-grande img { filter: invert(1); }

form.busca { flex: 1; max-width: 660px; display: flex; gap: 8px; align-items: center; }
.campo { position: relative; flex: 1; display: flex; align-items: center; }
.campo .ic-lupa {
  position: absolute; left: 15px; color: var(--texto-3);
  pointer-events: none; display: flex;
}
.campo input[type=text] {
  width: 100%; height: 44px;
  padding: 0 14px 0 44px;
  font-size: 14px; font-family: inherit;
  color: var(--texto); background: transparent;
  border: 1px solid var(--linha-forte); border-radius: 0;
  outline: none;
  transition: border-color .2s var(--curva);
}
.campo input[type=text]::placeholder { color: var(--texto-4); }
.campo input[type=text]:hover { border-color: var(--texto-3); }
.campo input[type=text]:focus { border-color: var(--texto); outline: none; }
.campo.aberto input[type=text] { border-bottom-color: transparent; }

.filtro { display: flex; flex: none; }
select {
  height: 44px; padding: 0 32px 0 12px; max-width: 200px;
  font-family: inherit; font-size: 13px;
  color: var(--texto-2); background: transparent;
  border: 1px solid var(--linha-forte); border-radius: 0;
  cursor: pointer; appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%),
                    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 17px) 20px, calc(100% - 12px) 20px;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  transition: border-color .2s var(--curva);
}
select:hover, select:focus { border-color: var(--texto); }
select option { background: var(--fundo); color: var(--texto); }

/* Botao cheio: preto e branco trocados. E o unico botao "forte" que existe. */
.botao-solido {
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  height: 44px; padding: 0 18px; flex: none;
  font-family: inherit; font-size: 13px; font-weight: 600;
  background: var(--solido); color: var(--sobre-solido);
  border: 1px solid var(--solido); border-radius: 0;
  cursor: pointer; text-decoration: none;
  transition: opacity .2s var(--curva);
}
.botao-solido:hover { opacity: .8; }
.botao-solido.quadrado { width: 44px; padding: 0; }

.icone-botao {
  height: 36px; width: 36px; flex: none;
  display: grid; place-items: center;
  border: 1px solid transparent; border-radius: 0;
  background: none; color: var(--texto-3);
  cursor: pointer; text-decoration: none;
  transition: color .2s var(--curva), background-color .2s var(--curva);
}
.icone-botao:hover { color: var(--texto); }
.icone-botao.ligada { background: var(--solido); color: var(--sobre-solido); }

.acoes { margin-left: auto; display: flex; align-items: center; gap: 2px; flex: none; }
.acoes .texto-accao {
  padding: 8px 12px; font-size: 12px; color: var(--texto-3);
  text-decoration: none; white-space: nowrap;
  transition: color .2s var(--curva);
}
.acoes .texto-accao:hover { color: var(--texto); }

/* ---------- pagina de entrada (codigo) ---------- */

.folha {
  margin: 0 auto; max-width: 1180px; min-height: 100vh;
  display: flex; flex-direction: column;
  padding: 28px 32px 28px;
}
.folha-topo {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  border-bottom: 1px solid var(--linha); padding-bottom: 20px;
}
.folha-topo .direita { display: flex; align-items: center; gap: 14px; }
.folha-meio { flex: 1; display: grid; place-items: center; padding: 56px 0; }
.entrada-caixa { width: 100%; max-width: 500px; }
.entrada-caixa .lead {
  margin: 26px 0 0; max-width: 355px;
  font-size: 16px; line-height: 1.75; color: var(--texto-2);
}
.entrada-forma {
  margin-top: 40px; padding: 20px 0;
  border-top: 1px solid var(--linha); border-bottom: 1px solid var(--linha);
}
.entrada-linha { display: flex; gap: 8px; margin-top: 12px; }
input.codigo {
  height: 56px; min-width: 0; flex: 1;
  padding: 0 16px;
  font-family: var(--mono); font-size: 14px; letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--texto); background: transparent;
  border: 1px solid var(--linha-forte); border-radius: 0;
  outline: none; transition: border-color .2s var(--curva);
}
input.codigo::placeholder { color: var(--texto-4); letter-spacing: .08em; }
input.codigo:focus { border-color: var(--texto); }
.entrada-forma .botao-solido { height: 56px; padding: 0 20px; font-size: 14px; }
.dica { margin: 12px 0 0; font-size: 12px; color: var(--texto-4); }
.dica.erro { color: var(--texto); }
input.codigo.errado { border-color: var(--texto); }
.nota-final {
  margin: 32px 0 0; max-width: 440px;
  font-size: 12px; line-height: 1.7; color: var(--texto-4);
}
.folha-rodape {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px;
  border-top: 1px solid var(--linha); padding-top: 20px;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}
.folha-rodape a { color: inherit; text-decoration: none; }
.folha-rodape a:hover { color: var(--texto-2); }

/* ---------- heroi da pagina inicial ---------- */

.envolve { margin: 0 auto; max-width: 1440px; padding: 0 32px; }
.heroi {
  position: relative; display: grid; place-items: center;
  min-height: calc(100vh - 72px); padding: 64px 0; overflow: hidden;
}
.heroi-gato {
  /* Fica preso a 76% da altura: a `contain` sozinha esticava-o de cima a
     baixo e o gato passava de textura a segundo assunto da pagina. */
  position: absolute; inset: 0 0 0 auto; width: 100%;
  background-repeat: no-repeat; background-position: right center;
  background-size: auto 76%;
  opacity: var(--gato-opacidade); pointer-events: none;
  filter: invert(var(--gato-inverter));
}
.heroi-dentro { position: relative; z-index: 1; width: 100%; max-width: 800px; }
.heroi .display { max-width: 680px; margin-top: 24px; }
.heroi .lead {
  margin: 28px 0 0; max-width: 470px;
  font-size: 16px; line-height: 1.75; color: var(--texto-2);
}
.heroi form.busca { max-width: 700px; margin-top: 44px; }
.heroi .campo input[type=text] { height: 60px; font-size: 16px; padding-left: 52px; }
.heroi .campo .ic-lupa { left: 20px; }
.heroi .botao-solido { height: 60px; padding: 0 22px; font-size: 14px; }
.heroi .filtro { order: 3; flex: 0 0 100%; margin-top: 12px; }
.heroi form.busca { flex-wrap: wrap; }
.heroi select { max-width: 260px; }
.experimente {
  margin-top: 20px; display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px 16px; font-size: 12px; color: var(--texto-3);
}
.experimente a {
  color: inherit; text-decoration: none;
  border-bottom: 1px solid var(--linha-forte); padding-bottom: 2px;
  transition: color .2s var(--curva), border-color .2s var(--curva);
}
.experimente a:hover { color: var(--texto); border-color: var(--texto); }

/* ---------- resultados ---------- */

.grelha-busca {
  display: grid; grid-template-columns: 230px minmax(0, 760px);
  gap: 48px; padding: 64px 0 0; align-items: start;
}
.lado .olho { margin-bottom: 20px; }
.lado-bloco { border-top: 1px solid var(--linha); padding-top: 16px; }
.lado-bloco label { display: block; font-size: 12px; color: var(--texto-3); margin-bottom: 8px; }
.lado select { width: 100%; max-width: none; height: 46px; }
.lado-nota { margin: 20px 0 0; font-size: 12px; line-height: 1.7; color: var(--texto-4); }

.abas {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-top: 20px; padding-bottom: 20px;
  border-bottom: 1px solid var(--linha);
}
.abas .aba {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 13px; font-size: 12px;
  color: var(--texto-3); text-decoration: none;
  border: 1px solid var(--linha); border-radius: 0;
  transition: color .2s var(--curva), border-color .2s var(--curva);
}
.abas .aba:hover { color: var(--texto); border-color: var(--texto-3); }
.abas .aba.ativa {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}
.abas .conta { opacity: .6; }

.resultado { border-bottom: 1px solid var(--linha); padding: 26px 0; }
.linha-origem {
  display: flex; align-items: center; gap: 9px; flex-wrap: wrap;
  margin-bottom: 12px;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}
.linha-origem .ponto {
  width: 3px; height: 3px; background: var(--texto-4); flex: none;
}
.titulo { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -.03em; line-height: 1.35; }
.titulo a {
  color: var(--texto); text-decoration: none;
  display: inline;
}
.titulo a:hover { text-decoration: underline; text-underline-offset: 4px; }
.titulo .ic { color: var(--texto-3); margin-left: 6px; }
.pontuacao { font-family: var(--mono); color: var(--texto-4); font-size: 11px; margin-left: 10px; }
.trecho { margin: 10px 0 0; max-width: 650px; font-size: 14px; line-height: 1.65; color: var(--texto-2); }
.trecho b { color: var(--texto); font-weight: 600; }
.paginas { margin: 12px 0 0; font-size: 12px; color: var(--texto-4); }

.prever {
  display: none; margin-top: 14px;
  align-items: center; gap: 7px;
  padding: 6px 12px; font-family: inherit; font-size: 12px;
  color: var(--texto-3); background: none;
  border: 1px solid var(--linha); border-radius: 0; cursor: pointer;
}
.prever:hover { color: var(--texto); border-color: var(--texto-3); }
.pv-inline:not(:empty) {
  border-left: 1px solid var(--linha-forte); padding: 4px 0 4px 16px; margin-top: 16px;
}
#painel {
  display: none; position: fixed; width: 330px;
  background: var(--cartao); color: var(--texto);
  border: 1px solid var(--linha-forte); border-radius: 0;
  padding: 18px 20px;
  max-height: 70vh; overflow-y: auto; z-index: 40;
}
.pv-etiquetas {
  margin: 0 0 8px; font-family: var(--mono); font-size: 10px;
  text-transform: uppercase; letter-spacing: .14em; color: var(--texto-4);
}
.pv-ficheiro { margin: 0; font-size: 13px; font-weight: 600; word-break: break-word; }
.pv-zip { margin: 4px 0 0; font-size: 11px; color: var(--texto-4); }
.pv-texto { margin: 14px 0 0; font-size: 13px; line-height: 1.7; color: var(--texto-2); }

.sugestao { margin: 0 0 20px; font-size: 14px; color: var(--texto-2); }
.sugestao b { color: var(--texto); font-weight: 600; }
.sugestao a { color: var(--texto); text-decoration: underline; text-underline-offset: 3px; }

.nada { padding: 72px 0; }
.nada .lead { margin: 14px 0 0; font-size: 14px; color: var(--texto-3); }

/* ---------- sugestoes da caixa de busca ---------- */

#sugestoes {
  display: none; position: absolute; left: 0; right: 0; top: 100%;
  background: var(--cartao);
  border: 1px solid var(--linha-forte); border-top: none; border-radius: 0;
  padding: 4px 0; z-index: 50;
  max-height: 320px; overflow-y: auto;
}
#sugestoes div {
  padding: 9px 16px; cursor: pointer; font-size: 14px;
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
}
#sugestoes div:hover, #sugestoes div.ativa { background: var(--suave); }
#sugestoes .fonte {
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .12em; color: var(--texto-4); white-space: nowrap;
}

/* ---------- paginacao ---------- */

.paginacao { margin: 40px 0 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.paginacao a, .paginacao span.atual {
  min-width: 40px; height: 40px;
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  padding: 0 12px; font-size: 13px; text-decoration: none;
  border: 1px solid var(--linha); border-radius: 0;
  color: var(--texto-3);
  transition: color .2s var(--curva), border-color .2s var(--curva);
}
.paginacao a:hover { color: var(--texto); border-color: var(--texto-3); }
.paginacao span.atual {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}
.paginacao .resumo {
  width: 100%; margin-top: 14px; padding: 0; min-width: 0; height: auto;
  border: none; background: none; display: block;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}

/* ---------- paginas de apoio ---------- */

.pagina-apoio { margin: 0 auto; max-width: 980px; padding: 48px 32px 0; }
.pagina-apoio .voltar {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 12px; color: var(--texto-3); text-decoration: none;
}
.pagina-apoio .voltar:hover { color: var(--texto); }
.pagina-apoio .olho { margin-top: 48px; }
.pagina-apoio .display { margin-top: 12px; }

.metricas {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-top: 40px;
  border-top: 1px solid var(--linha); border-left: 1px solid var(--linha);
}
.metrica {
  border-right: 1px solid var(--linha); border-bottom: 1px solid var(--linha);
  padding: 18px 16px; min-height: 116px;
}
.metrica .numero { font-size: 30px; font-weight: 600; letter-spacing: -.05em; display: block; }
.metrica .rotulo { margin-top: 8px; font-size: 12px; color: var(--texto-3); }

.duas-colunas { display: grid; gap: 56px; margin-top: 64px; grid-template-columns: 1.35fr .65fr; }
.grafico { margin-top: 20px; border-bottom: 1px solid var(--linha); }
.grafico svg { display: block; width: 100%; height: auto; }
.lista-topo { margin: 16px 0 0; padding: 0; list-style: none; border-top: 1px solid var(--linha); }
.lista-topo li {
  display: flex; justify-content: space-between; gap: 16px; align-items: baseline;
  border-bottom: 1px solid var(--linha); padding: 12px 0; font-size: 14px;
}
.lista-topo .ordem { font-family: var(--mono); font-size: 11px; color: var(--texto-4); }
.lista-topo a { text-decoration: none; }
.lista-topo a:hover { text-decoration: underline; text-underline-offset: 3px; }

.bloco-linhas {
  margin-top: 48px; padding: 28px 0;
  border-top: 1px solid var(--linha); border-bottom: 1px solid var(--linha);
}
.bloco-linhas p { margin: 0; }
.bloco-linhas .grande { font-size: 18px; color: var(--texto-2); }
.bloco-linhas .pequena { margin-top: 8px; font-size: 13px; color: var(--texto-4); }

.temas { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.temas .tema {
  display: inline-block; padding: 7px 13px; font-size: 12px;
  color: var(--texto-3); text-decoration: none;
  border: 1px solid var(--linha); border-radius: 0;
  transition: color .2s var(--curva), border-color .2s var(--curva);
}
.temas .tema:hover { color: var(--texto); border-color: var(--texto-3); }
ul.dsc, ul.novo-lista { list-style: none; padding: 0; margin: 16px 0 0; }
ul.dsc li, ul.novo-lista li {
  display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap;
  border-bottom: 1px solid var(--linha); padding: 13px 0; font-size: 14px;
}
ul.dsc a, ul.novo-lista a { color: var(--texto); text-decoration: none; }
ul.dsc a:hover, ul.novo-lista a:hover { text-decoration: underline; text-underline-offset: 3px; }
.vezes, ul.novo-lista .quando {
  margin-left: auto; font-family: var(--mono); font-size: 10px;
  text-transform: uppercase; letter-spacing: .12em; color: var(--texto-4);
}
.disciplina {
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .12em; color: var(--texto-3);
  border: 1px solid var(--linha); padding: 2px 7px;
}
.novo {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin: 0 0 28px; padding: 14px 0;
  border-top: 1px solid var(--linha); border-bottom: 1px solid var(--linha);
  font-size: 13px; color: var(--texto-2);
}
.novo a { color: var(--texto); text-decoration: underline; text-underline-offset: 3px; }

.lista-docs li { display: block; padding: 18px 0; }
.lista-docs a { display: inline-flex; align-items: center; gap: 9px; font-weight: 500; }
.lista-docs .quando { margin-left: 10px; }
.doc-diz { margin: 6px 0 0; font-size: 13px; color: var(--texto-3); max-width: 60ch; }

footer.rodape {
  margin: 80px auto 0; max-width: 1440px;
  padding: 22px 32px 28px;
  border-top: 1px solid var(--linha);
  display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: .14em; color: var(--texto-4);
}
footer.rodape a { color: inherit; text-decoration: none; }
footer.rodape a:hover { color: var(--texto-2); }

/* O credito e o unico item do rodape com duas alturas: a marca por cima e o
   rotulo por baixo. `align-items: center` nos rodapes mantem as outras
   entradas centradas contra ele em vez de coladas ao topo. */
.credito {
  display: inline-flex; flex-direction: column; align-items: center; gap: 5px;
  color: var(--texto-4); line-height: 1;
  transition: color .2s var(--curva);
}
.credito:hover { color: var(--texto); }
.credito span { letter-spacing: .14em; }
footer.rodape, .folha-rodape { align-items: center; }

/* ---------- tablet ---------- */

@media (max-width: 1080px) {
  .grelha-busca { grid-template-columns: 200px minmax(0, 1fr); gap: 32px; }
  .duas-colunas { grid-template-columns: 1fr; gap: 40px; }
}

/* ---------- telemovel ---------- */

@media (max-width: 820px) {
  .topo-linha { flex-wrap: wrap; gap: 10px; padding: 12px 18px; min-height: 0; }
  /* So no CABECALHO. Sem o `.topo` a frente, o `order` caia tambem no
     formulario do heroi, onde a coluna e vertical, e empurrava a barra de
     busca para depois do resto. */
  .topo form.busca { order: 3; flex-basis: 100%; max-width: none; }
  /* `1 1 auto` e nao `1 1 100%`: o seletor de disciplina saiu do cabecalho e
     passou a viver so na coluna de filtros, portanto a caixa ja nao precisa
     da linha inteira - e com 100% empurrava o botao sozinho para baixo. */
  .topo form.busca .campo { flex: 1 1 auto; }
  .acoes { order: 2; }

  .envolve, .pagina-apoio { padding-left: 18px; padding-right: 18px; }
  .folha { padding: 20px 18px; }
  .grelha-busca { grid-template-columns: 1fr; gap: 28px; padding-top: 32px; }
  /* No telemovel o filtro nao merece uma coluna inteira em cima dos
     resultados: encolhe para uma linha so. */
  .lado { display: flex; align-items: flex-end; gap: 12px; }
  .lado .olho { display: none; }
  .lado-bloco { border-top: none; padding-top: 0; flex: 1; }

  .heroi { min-height: 0; padding: 48px 0 56px; }
  .heroi-gato { display: none; }
  .heroi form.busca { margin-top: 32px; }
  .heroi .campo input[type=text] { height: 52px; }
  .heroi .botao-solido { height: 52px; }
  .entrada-linha { flex-wrap: wrap; }
  .entrada-forma .botao-solido { width: 100%; }

  .duas-colunas { margin-top: 44px; }
  .metricas { grid-template-columns: repeat(2, 1fr); }
  #painel { display: none !important; }
  .prever { display: inline-flex; }
  /* Cabiam tres resultados por ecra. O trecho corta-se a duas linhas: chega
     para reconhecer o documento e o aluno ve o dobro da lista sem deslizar. */
  .trecho {
    display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
  }
  .resultado { padding: 20px 0; }
  .titulo { font-size: 17px; }
  footer.rodape { padding: 20px 18px 24px; }
}

/* ---------- telao da sala ---------- */

/* Num projetor a pagina e vista de longe e a sala tem luz. O corpo cresce e
   os cinzentos mais fracos sobem um degrau, senao o trecho nao se le da
   terceira fila. */
@media (min-width: 1600px) {
  body { font-size: 17px; }
  .trecho { font-size: 16px; color: var(--texto-2); }
  .titulo { font-size: 23px; }
  .olho, .linha-origem { font-size: 11px; }
  .grelha-busca { grid-template-columns: 260px minmax(0, 900px); }
}
"""

# Corre antes de a pagina ser pintada. Sem isto, quem escolheu um tema ve um
# relampago do outro a cada navegacao enquanto o CSS ainda nao aplicou.
GUIAO_TEMA = """
(function(){try{var t=localStorage.getItem("tema");
if(t==="claro"||t==="escuro"){document.documentElement.setAttribute("data-tema",t);}
}catch(e){}})();
"""

GUIAO_BOTAO_TEMA = """
(function () {
  var raiz = document.documentElement;
  var botao = document.getElementById("botao-tema");
  if (!botao) { return; }
  var sol = botao.querySelector(".ic-sol");
  var lua = botao.querySelector(".ic-lua");
  function escuroAgora() {
    var posto = raiz.getAttribute("data-tema");
    if (posto) { return posto === "escuro"; }
    return !window.matchMedia("(prefers-color-scheme: light)").matches;
  }
  function rotular() {
    var escuro = escuroAgora();
    if (sol) { sol.style.display = escuro ? "" : "none"; }
    if (lua) { lua.style.display = escuro ? "none" : ""; }
    var diz = escuro ? "Ativar modo claro" : "Ativar modo escuro";
    botao.setAttribute("aria-label", diz);
    botao.setAttribute("title", diz);
  }
  botao.addEventListener("click", function () {
    var novo = escuroAgora() ? "claro" : "escuro";
    raiz.setAttribute("data-tema", novo);
    try { localStorage.setItem("tema", novo); } catch (e) {}
    rotular();
  });
  rotular();
})();
"""


def cabeca(titulo: str) -> str:
    """O <head> comum a todas as paginas."""
    return (
        "<!doctype html>\n"
        '<html lang="pt-pt">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{titulo}</title>\n"
        '<link rel="icon" type="image/png" href="/estatico/icone.png">\n'
        # As duas fontes que aparecem acima da dobra em todas as paginas.
        '<link rel="preload" as="font" type="font/woff2" crossorigin '
        'href="/estatico/manrope.woff2">\n'
        '<link rel="preload" as="font" type="font/woff2" crossorigin '
        'href="/estatico/libre-bodoni.woff2">\n'
        f"<script>{GUIAO_TEMA}</script>\n"
        f"<style>{CSS}</style>\n"
        "</head>"
    )


def marca(grande: bool = False) -> str:
    """O gato e o lettering. Em pequeno leva ao inicio; em grande e so imagem."""
    if grande:
        return (
            '<div class="marca-grande">'
            '<img class="gato" src="/estatico/gato.png" alt="">'
            '<img class="nome" src="/estatico/lettering.png" alt="Madalena Search">'
            "</div>"
        )
    return (
        '<a class="marca" href="/">'
        '<img class="gato" src="/estatico/gato.png" alt="">'
        '<img class="nome" src="/estatico/lettering.png" alt="Madalena Search">'
        "</a>"
    )


def botao_tema() -> str:
    """Um so botao com os dois icones; o guiao esconde o que nao serve.

    Trocar o `<svg>` por JavaScript obrigaria a ter o desenho em duas linguas,
    aqui e la. Assim ha um `display:none` e o desenho vive so num sitio.
    """
    return (
        '<button type="button" class="icone-botao" id="botao-tema" '
        'aria-label="mudar de tema">'
        f'<span class="ic-sol">{icones.svg("sol", 16)}</span>'
        f'<span class="ic-lua">{icones.svg("lua", 16)}</span>'
        "</button>"
    )


def acoes(pagina: str = "busca") -> str:
    """Os botoes do canto superior direito.

    O `sair` fecha a sessao e fica no canto - nao no rodape, onde estava:
    numa pagina de resultados o rodape fica a dez rolamentos de distancia.
    """
    novidades = " ligada" if pagina == "novidades" else ""
    estatisticas = " ligada" if pagina == "estatisticas" else ""
    return (
        '<div class="acoes">'
        f"{som.botao()}{botao_tema()}"
        f'<a class="texto-accao{novidades}" href="/novidades">novidades</a>'
        f'<a class="icone-botao{estatisticas}" href="/estatisticas" '
        f'title="estatísticas" aria-label="estatísticas">{icones.svg("grafico", 16)}</a>'
        '<a class="icone-botao" href="/sair" title="sair" aria-label="sair">'
        f'{icones.svg("sair", 16)}</a>'
        "</div>"
    )


AUTOR = "https://github.com/EduhxH"


def credito() -> str:
    """A marca do GitHub com o rotulo por baixo, para os dois rodapes.

    `rel="noopener noreferrer"` porque abre noutro separador: sem `noopener` a
    pagina de destino ganha uma referencia a esta e podia navega-la.
    """
    return (
        f'<a class="credito" href="{AUTOR}" target="_blank" '
        'rel="noopener noreferrer" title="EduhxH no GitHub">'
        f'{icones.svg("github", 15)}<span>Autor</span></a>'
    )


def rodape() -> str:
    """As marcas em monoespacado, como no desenho, mais o credito."""
    return (
        '<footer class="rodape">'
        "<span>Índice local</span>"
        "<span>Sem serviços externos</span>"
        '<span><a href="/novidades">Material novo</a></span>'
        '<span><a href="/privacidade">Os teus dados</a></span>'
        f"{credito()}"
        "</footer>"
    )
