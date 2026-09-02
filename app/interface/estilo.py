"""Folha de estilo e esqueleto das paginas.

Vive fora de `web.py` porque sao duas coisas de natureza diferente: aqui e
aparencia, la e o que o servidor faz.

O sistema visual e **monocromatico**: uma so escala de cinzentos, sem cor de
realce nenhuma. Nao e economia - e o que faz o gato preto do logotipo ser a
unica coisa com carater na pagina. Onde faltaria cor para separar as coisas,
separa-as a escala: uma superficie um degrau acima, uma linha de 1px, mais
espaco.

Tres ideias mandam no ficheiro:

1. **Uma escala de doze degraus, dos dois lados.** Os mesmos doze valores
   servem o tema claro e o escuro, invertidos. Cada simbolo (`--texto`,
   `--linha`, `--superficie`...) aponta para um degrau; mudar de tema e mudar
   para onde apontam, nao inventar cores novas.
2. **O tema tem tres estados, nao dois.** Claro, escuro, e "o que o sistema
   disser" - o estado de quem nunca mexeu no botao. Por isso o escuro aparece
   em dois blocos: um por `prefers-color-scheme` para quem nao escolheu,
   outro por `data-tema` para quem escolheu.
3. **Contraste medido, nao adivinhado.** A escala e a que veio na referencia,
   dada como AAA. `--texto` sobre `--fundo` da 19:1 no claro e 18:1 no
   escuro; `--texto-2`, o cinzento dos trechos, fica em 7:1 dos dois lados -
   acima dos 4.5:1 que a norma pede para texto pequeno.
"""

from app.interface import icones

CSS = """
:root {
  color-scheme: light;

  /* escala neutra - clara */
  --n0:  #ffffff;  --n50: #fafafa;  --n100:#f5f5f5;  --n200:#e5e5e5;
  --n300:#d4d4d4;  --n400:#a3a3a3;  --n500:#737373;  --n600:#525252;
  --n700:#404040;  --n800:#262626;  --n900:#171717;  --n950:#0a0a0a;

  --fundo: var(--n50);
  --superficie: var(--n0);
  --superficie-2: var(--n100);
  --linha: var(--n200);
  --linha-forte: var(--n300);
  --texto: var(--n950);
  --texto-2: var(--n600);
  --texto-3: var(--n400);
  --solido: var(--n900);
  --sobre-solido: var(--n0);
  --sombra: 0 1px 2px rgba(10,10,10,.04), 0 8px 24px rgba(10,10,10,.06);

  --r-s: 8px;
  --r-m: 12px;
  --r-g: 16px;
  --r-pastilha: 999px;
  --curva: cubic-bezier(.4, 0, .2, 1);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="claro"]) {
    color-scheme: dark;
    --n0:  #000000;  --n50: #0a0a0a;  --n100:#171717;  --n200:#262626;
    --n300:#373737;  --n400:#525252;  --n500:#8a8a8a;  --n600:#a3a3a3;
    --n700:#d4d4d4;  --n800:#e5e5e5;  --n900:#f5f5f5;  --n950:#fafafa;
    --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.5);
  }
}
:root[data-tema="escuro"] {
  color-scheme: dark;
  --n0:  #000000;  --n50: #0a0a0a;  --n100:#171717;  --n200:#262626;
  --n300:#373737;  --n400:#525252;  --n500:#8a8a8a;  --n600:#a3a3a3;
  --n700:#d4d4d4;  --n800:#e5e5e5;  --n900:#f5f5f5;  --n950:#fafafa;
  --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.5);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--fundo);
  color: var(--texto);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  font-size: 15px; line-height: 1.6;
  letter-spacing: -.005em;
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}
a { color: inherit; }
img { max-width: 100%; }
.ic { flex: none; vertical-align: middle; }

/* Quem prefere menos movimento nao leva nenhum. Vale para o CSS e o guiao
   das animacoes le a mesma preferencia. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .001ms !important;
    transition-duration: .001ms !important;
  }
}

/* ---------- topo ---------- */

.topo {
  position: sticky; top: 0; z-index: 30;
  background: color-mix(in srgb, var(--fundo) 88%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  -webkit-backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--linha);
}
.topo-linha { display: flex; align-items: center; gap: 20px; padding: 12px 22px; }
.marca { display: flex; align-items: center; gap: 8px; text-decoration: none; flex: none; }
.marca img.gato { height: 30px; width: auto; }
.marca img.nome { height: 15px; width: auto; }

/* O desenho e preto chapado. Em fundo escuro inverte-se, em vez de guardar
   um segundo ficheiro que depois fica por atualizar. */
:root[data-tema="escuro"] .marca img,
:root[data-tema="escuro"] .marca-grande img,
:root[data-tema="escuro"] .vazio-marca img { filter: invert(1); }
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="claro"]) .marca img,
  :root:not([data-tema="claro"]) .marca-grande img,
  :root:not([data-tema="claro"]) .vazio-marca img { filter: invert(1); }
}

form.busca { flex: 1; max-width: 620px; display: flex; gap: 8px; align-items: center; }
.campo { position: relative; flex: 1; display: flex; align-items: center; }
.campo .ic-lupa {
  position: absolute; left: 14px; color: var(--texto-3);
  pointer-events: none; display: flex;
}
.campo input[type=text] {
  width: 100%; height: 42px;
  padding: 0 14px 0 42px;
  font-size: 15px; font-family: inherit;
  color: var(--texto); background: var(--superficie);
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  outline: none;
  transition: border-color .18s var(--curva), box-shadow .18s var(--curva);
}
.campo input[type=text]::placeholder { color: var(--texto-3); }
.campo input[type=text]:hover { border-color: var(--linha-forte); }
.campo input[type=text]:focus {
  border-color: var(--texto-3);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--texto-3) 16%, transparent);
}
.campo.aberto input[type=text] {
  border-radius: var(--r-g) var(--r-g) 0 0;
  border-bottom-color: transparent; box-shadow: none;
}
.filtro { display: flex; flex: none; }
select {
  height: 42px; padding: 0 30px 0 12px; max-width: 190px;
  font-family: inherit; font-size: 13px;
  color: var(--texto-2); background: var(--superficie);
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  cursor: pointer; appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%),
                    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 16px) 19px, calc(100% - 11px) 19px;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}
select:hover { border-color: var(--linha-forte); }

/* Botao redondo so com icone: o feitio do topo e das accoes. */
.icone-botao {
  height: 38px; width: 38px; flex: none;
  display: grid; place-items: center;
  border: 1px solid transparent; border-radius: var(--r-pastilha);
  background: none; color: var(--texto-2);
  cursor: pointer; font-family: inherit;
  text-decoration: none;
  transition: background-color .18s var(--curva), color .18s var(--curva);
}
.icone-botao:hover { background: var(--superficie-2); color: var(--texto); }
.icone-botao.solido {
  background: var(--solido); color: var(--sobre-solido);
  border-color: var(--solido);
}
.icone-botao.solido:hover { background: var(--texto); color: var(--sobre-solido); }
button.lupa { height: 42px; width: 42px; }

.acoes { margin-left: auto; display: flex; align-items: center; gap: 4px; flex: none; }

/* ---------- separadores das seccoes ---------- */

.abas {
  display: flex; gap: 8px; padding: 0 22px 12px;
  overflow-x: auto; scrollbar-width: none;
}
.abas::-webkit-scrollbar { display: none; }
.abas .aba {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 13px; color: var(--texto-2); text-decoration: none;
  white-space: nowrap; padding: 7px 14px;
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  background: var(--superficie);
  transition: background-color .18s var(--curva), color .18s var(--curva),
              border-color .18s var(--curva);
}
.abas .aba:hover { border-color: var(--linha-forte); color: var(--texto); }
.abas .aba.ativa {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}
.abas .conta {
  font-size: 11px; color: var(--texto-3);
  background: var(--superficie-2); border-radius: var(--r-pastilha);
  padding: 0 7px; line-height: 17px;
}
.abas .aba.ativa .conta {
  background: color-mix(in srgb, var(--sobre-solido) 18%, transparent);
  color: var(--sobre-solido);
}

/* ---------- corpo ---------- */

main { padding: 26px 22px 0; }
.coluna { max-width: 700px; margin: 0 auto; }

.meta { color: var(--texto-3); font-size: 13px; margin: 0 0 18px; }
.sugestao { font-size: 14px; color: var(--texto-2); margin: 0 0 18px; }
.sugestao b { color: var(--texto); font-weight: 600; }
.sugestao a { color: var(--texto); text-decoration: underline; text-underline-offset: 3px; }

.resultado {
  background: var(--superficie);
  border: 1px solid var(--linha);
  border-radius: var(--r-m);
  padding: 15px 17px; margin-bottom: 10px;
  transition: border-color .18s var(--curva), background-color .18s var(--curva);
}
.resultado:hover { border-color: var(--linha-forte); background: var(--superficie); }
.linha-origem {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  font-size: 12px; color: var(--texto-3); margin-bottom: 6px;
}
.linha-origem .ic { color: var(--texto-3); }
.linha-origem .sep { color: var(--linha-forte); }
.linha-origem .disciplina {
  color: var(--texto-2); border: 1px solid var(--linha);
  border-radius: var(--r-pastilha); padding: 1px 9px;
}
.titulo { font-size: 16px; font-weight: 600; line-height: 1.4; margin: 0 0 4px; }
.titulo a {
  color: var(--texto); text-decoration: none;
  display: inline-flex; align-items: baseline; gap: 6px;
}
.titulo a:hover { text-decoration: underline; text-underline-offset: 3px; }
.titulo a:visited { color: var(--texto-2); }
.pontuacao { color: var(--texto-3); font-size: 12px; margin-left: 8px; }
.trecho { margin: 0; font-size: 14px; line-height: 1.6; color: var(--texto-2); }
.trecho b { color: var(--texto); font-weight: 600; }
.paginas { margin: 8px 0 0; font-size: 12px; color: var(--texto-3); }
.vazio { color: var(--texto-2); font-size: 15px; }

.prever {
  display: none; margin-top: 10px;
  align-items: center; gap: 6px;
  font-size: 12px; font-family: inherit;
  color: var(--texto-2); background: var(--superficie-2);
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  padding: 5px 12px; cursor: pointer;
}
.prever:hover { color: var(--texto); border-color: var(--linha-forte); }
.pv-inline:not(:empty) {
  border-left: 2px solid var(--linha); padding: 6px 0 2px 14px; margin-top: 12px;
}
#painel {
  display: none; position: fixed; width: 330px;
  background: var(--superficie); color: var(--texto);
  border: 1px solid var(--linha); border-radius: var(--r-g);
  box-shadow: var(--sombra);
  padding: 16px 18px;
  max-height: 70vh; overflow-y: auto; z-index: 40;
}
.pv-etiquetas { margin: 0 0 6px; font-size: 11px; color: var(--texto-3); }
.pv-ficheiro { margin: 0; font-size: 13px; font-weight: 600; word-break: break-word; }
.pv-zip { margin: 3px 0 0; font-size: 11px; color: var(--texto-3); }
.pv-texto { margin: 12px 0 0; font-size: 13px; line-height: 1.6; color: var(--texto-2); }

/* ---------- sugestoes da caixa de busca ---------- */

#sugestoes {
  display: none; position: absolute; left: 0; right: 0; top: 100%;
  background: var(--superficie);
  border: 1px solid var(--linha); border-top: none;
  border-radius: 0 0 var(--r-g) var(--r-g);
  box-shadow: var(--sombra);
  padding: 6px; z-index: 50;
  max-height: 320px; overflow-y: auto;
}
#sugestoes div {
  padding: 8px 12px; cursor: pointer; font-size: 14px;
  border-radius: var(--r-s);
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
}
#sugestoes div:hover, #sugestoes div.ativa { background: var(--superficie-2); }
#sugestoes .fonte { font-size: 11px; color: var(--texto-3); white-space: nowrap; }

/* ---------- paginacao ---------- */

.paginacao { margin: 32px 0 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.paginacao a, .paginacao span.atual {
  min-width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 0 10px; font-size: 13px; text-decoration: none;
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  color: var(--texto-2); background: var(--superficie);
  transition: border-color .18s var(--curva), color .18s var(--curva);
}
.paginacao a:hover { border-color: var(--linha-forte); color: var(--texto); }
.paginacao span.atual {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}
.paginacao .resumo {
  width: 100%; margin-top: 12px; padding: 0;
  font-size: 12px; color: var(--texto-3);
  border: none; background: none; display: block; min-width: 0; height: auto;
}

/* ---------- pagina inicial e entrada ---------- */

/* `form.busca` traz `flex: 1` para o topo dos resultados, onde tem de
   esticar. Ao centro a coluna e vertical, e esse mesmo `flex: 1` esticava o
   formulario em altura ate 356px, com a caixa a boiar no meio. */
.centro {
  min-height: 84vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 24px 22px 60px; text-align: center;
}
.centro.cheio { min-height: 100vh; }
.centro form.busca { flex: none; width: 100%; max-width: 560px; flex-wrap: wrap; }
.centro .campo input[type=text] { height: 52px; font-size: 16px; padding-left: 46px; }
.centro .campo .ic-lupa { left: 17px; }
.centro button.lupa { height: 52px; width: 52px; }
/* Quem decide a mudanca de linha e o tamanho hipotetico ja limitado pelo
   `max-width`: um `select` com `flex-basis:100%; max-width:220px` volta a
   caber na linha de cima e nunca desce. O `<span>` e que ocupa a linha. */
.centro form.busca .filtro {
  order: 3; flex: 0 0 100%; justify-content: center; margin-top: 14px;
}
.centro form.busca select { height: 38px; max-width: 220px; }

.marca-grande { margin-bottom: 22px; }
.marca-grande img.gato { height: 84px; width: auto; display: block; margin: 0 auto 12px; }
.marca-grande img.nome { height: 20px; width: auto; }
.lema {
  font-size: 32px; font-weight: 700; line-height: 1.15;
  letter-spacing: -.03em; margin: 0 0 8px; color: var(--texto);
}
.sublema {
  font-size: 15px; color: var(--texto-2); margin: 0 0 30px; max-width: 460px;
}
.centro .abaixo {
  margin-top: 30px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;
}
.pastilha {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: inherit; font-size: 13px; text-decoration: none;
  color: var(--texto-2); background: var(--superficie);
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  padding: 8px 15px; cursor: pointer;
  transition: border-color .18s var(--curva), color .18s var(--curva);
}
.pastilha:hover { border-color: var(--linha-forte); color: var(--texto); }
.pastilha.solida {
  background: var(--solido); color: var(--sobre-solido); border-color: var(--solido);
}

.cartao-entrada {
  width: 100%; max-width: 400px;
  background: var(--superficie);
  border: 1px solid var(--linha); border-radius: var(--r-g);
  box-shadow: var(--sombra);
  padding: 30px 28px;
}
.cartao-entrada form { width: 100%; }
.etiqueta-beta {
  display: inline-flex; align-items: center; gap: 6px;
  margin: 0 0 18px;
  background: var(--superficie-2); color: var(--texto-2);
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  font-size: 11px; letter-spacing: .02em; padding: 4px 11px;
}
.cartao-entrada .diz { font-size: 14px; color: var(--texto-2); margin: 0 0 22px; }
input.codigo {
  width: 100%; height: 48px; padding: 0 14px;
  text-align: center; letter-spacing: .18em; text-transform: uppercase;
  font-size: 15px; font-family: inherit; color: var(--texto);
  background: var(--fundo);
  border: 1px solid var(--linha); border-radius: var(--r-m);
  outline: none;
  transition: border-color .18s var(--curva), box-shadow .18s var(--curva);
}
input.codigo::placeholder { color: var(--texto-3); letter-spacing: .18em; }
input.codigo:focus {
  border-color: var(--texto-3);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--texto-3) 16%, transparent);
}
.botao-entrar {
  width: 100%; margin-top: 10px; height: 46px;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  font-family: inherit; font-size: 14px; font-weight: 500;
  background: var(--solido); color: var(--sobre-solido);
  border: 1px solid var(--solido); border-radius: var(--r-m);
  cursor: pointer;
  transition: opacity .18s var(--curva);
}
.botao-entrar:hover { opacity: .88; }
.erro { color: var(--texto); font-size: 13px; margin: 16px 0 0; }
.aviso {
  margin-top: 26px; max-width: 400px; text-align: left;
  color: var(--texto-3); font-size: 12px; line-height: 1.7;
}
.aviso b { color: var(--texto-2); font-weight: 600; }

.vazio-marca { margin: 26px 0 18px; }
.vazio-marca img { height: 132px; width: auto; opacity: .5; }

/* ---------- paginas de apoio ---------- */

h2.sec, h2.dsc, h2 {
  font-size: 13px; font-weight: 600; color: var(--texto-3);
  letter-spacing: .04em; text-transform: uppercase;
  margin: 34px 0 14px; padding-bottom: 10px;
  border-bottom: 1px solid var(--linha);
  display: flex; justify-content: space-between; align-items: baseline;
}
h2.sec .conta { color: var(--texto-3); font-size: 12px; letter-spacing: 0; }
.voltar { font-size: 13px; margin: 0 0 20px; }
.voltar a { color: var(--texto-2); text-decoration: none; }
.voltar a:hover { color: var(--texto); }
.temas { display: flex; flex-wrap: wrap; gap: 8px; }
.temas .tema {
  display: inline-block; border: 1px solid var(--linha);
  border-radius: var(--r-pastilha);
  padding: 6px 14px; font-size: 13px;
  color: var(--texto-2); text-decoration: none; background: var(--superficie);
  transition: border-color .18s var(--curva), color .18s var(--curva);
}
.temas .tema:hover { border-color: var(--linha-forte); color: var(--texto); }
ul.dsc { list-style: none; padding: 0; margin: 0; font-size: 14px; line-height: 2.1; }
ul.dsc a { color: var(--texto-2); text-decoration: none; }
ul.dsc a:hover { color: var(--texto); text-decoration: underline; text-underline-offset: 3px; }
.vezes { color: var(--texto-3); font-size: 11px; }
.novo {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--texto-2);
  background: var(--superficie); border: 1px solid var(--linha);
  border-radius: var(--r-m); padding: 12px 15px; margin: 0 0 22px;
}
.novo a { color: var(--texto); text-decoration: underline; text-underline-offset: 3px; }
ul.novo-lista { list-style: none; padding: 0; margin: 0; }
ul.novo-lista li {
  padding: 12px 0; border-bottom: 1px solid var(--linha); font-size: 14px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
ul.novo-lista a { color: var(--texto); text-decoration: none; }
ul.novo-lista a:hover { text-decoration: underline; text-underline-offset: 3px; }
ul.novo-lista .quando { color: var(--texto-3); font-size: 12px; margin-left: auto; }
.disciplina {
  color: var(--texto-2); font-size: 12px;
  border: 1px solid var(--linha); border-radius: var(--r-pastilha);
  padding: 1px 9px;
}

/* ---------- estatisticas ---------- */

.titulo-pagina {
  font-size: 26px; font-weight: 700; letter-spacing: -.025em; margin: 0 0 4px;
}
.cartoes {
  display: grid; gap: 10px; margin: 22px 0;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
}
.cartao {
  background: var(--superficie); border: 1px solid var(--linha);
  border-radius: var(--r-m); padding: 15px 16px;
}
.cartao .numero {
  font-size: 24px; font-weight: 600; letter-spacing: -.02em;
  color: var(--texto); display: block; line-height: 1.2;
}
.cartao .rotulo { font-size: 11px; color: var(--texto-3); margin-top: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border-bottom: 1px solid var(--linha); padding: 10px 8px; text-align: left; }
th { color: var(--texto-3); font-weight: 500; font-size: 11px; letter-spacing: .03em; }
td { color: var(--texto-2); }
.resumo { font-size: 14px; color: var(--texto-2); margin: 6px 0 0; }

footer {
  margin-top: 70px; border-top: 1px solid var(--linha);
  padding: 20px 22px 26px; color: var(--texto-3); font-size: 12px;
}
footer a { color: var(--texto-3); text-decoration: none; }
footer a:hover { color: var(--texto-2); }

/* ---------- ecra estreito ---------- */

@media (max-width: 899px) {
  .topo-linha { flex-wrap: wrap; gap: 10px; padding: 10px 14px; }
  /* Numa linha so, a caixa de escrever ficava com 150px e o filtro com 130:
     lia-se "criterios de avali" e mais nada. A caixa passa a ocupar a linha
     inteira e o filtro desce para a linha de baixo. */
  form.busca {
    order: 3; width: 100%; max-width: none; flex-basis: 100%; flex-wrap: wrap;
  }
  form.busca .campo { flex: 1 1 100%; }
  form.busca .filtro { flex: 1; }
  form.busca select { width: 100%; max-width: none; height: 38px; }
  form.busca button.lupa { height: 38px; width: 42px; }
  .acoes { order: 2; }
  .abas { padding: 0 14px 12px; }
  main { padding: 20px 14px 0; }
  #painel { display: none !important; }
  .prever { display: inline-flex; }
  /* Cabiam tres resultados por ecra. O trecho corta-se a duas linhas: chega
     para reconhecer o documento e o aluno ve o dobro da lista sem deslizar. */
  .trecho {
    display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
  }
  .lema { font-size: 26px; }
  .marca-grande img.gato { height: 68px; }
  .titulo-pagina { font-size: 22px; }
}
"""

# Corre antes de a pagina ser pintada. Sem isto, quem escolheu o tema escuro
# ve um relampago claro a cada navegacao enquanto o CSS ainda nao aplicou.
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
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function rotular() {
    var escuro = escuroAgora();
    if (sol) { sol.style.display = escuro ? "" : "none"; }
    if (lua) { lua.style.display = escuro ? "none" : ""; }
    botao.setAttribute("aria-label", escuro ? "tema claro" : "tema escuro");
    botao.setAttribute("title", escuro ? "tema claro" : "tema escuro");
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
        f'<span class="ic-sol">{icones.svg("sol")}</span>'
        f'<span class="ic-lua">{icones.svg("lua")}</span>'
        "</button>"
    )


def acoes(sair: bool = True, voltar: bool = False) -> str:
    """Os botoes do canto superior direito.

    O `sair` fecha a sessao e fica no canto - nao no rodape, onde estava:
    numa pagina de resultados o rodape fica a dez rolamentos de distancia.
    """
    partes = [botao_tema()]
    if voltar:
        partes.append(
            '<a class="icone-botao" href="/" title="busca" aria-label="busca">'
            f'{icones.svg("lupa")}</a>'
        )
    else:
        partes.append(
            '<a class="icone-botao" href="/estatisticas" title="estatisticas" '
            f'aria-label="estatisticas">{icones.svg("grafico")}</a>'
        )
    if sair:
        partes.append(
            '<a class="icone-botao" href="/sair" title="sair" aria-label="sair">'
            f'{icones.svg("sair")}</a>'
        )
    return f'<div class="acoes">{"".join(partes)}</div>'

