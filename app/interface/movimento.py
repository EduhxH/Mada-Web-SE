"""As animacoes das paginas, em cima do anime.js.

O ficheiro `assets/js/anime.min.js` e a versao 4.1.4, licenca MIT, descarregada
uma vez e **servida pela propria maquina** - vale a regra do resto do projeto:
em execucao nao se vai buscar nada a servidores alheios.

Quatro regras mandam nas animacoes daqui:

1. **Nada fica escondido a espera de uma animacao que talvez nao venha.**
   Esta e a regra que custou um erro a descobrir. Uma entrada em cascata
   comeca por por os elementos a `opacity: 0` - e a partir dai a pagina so e
   legivel se a animacao chegar ao fim.

   **Numa pagina aberta em separador escondido, ela nunca chega.** Nao e
   feitio do anime.js: o `requestAnimationFrame`, que e o relogio de qualquer
   biblioteca de animacao, nao dispara enquanto o documento esta escondido.
   E uma regra do browser e nao ha biblioteca que lhe fuja. Um ctrl+clique ou
   uma sessao restaurada davam uma pagina em branco ate o aluno olhar para
   ela.

   Sao precisas duas defesas, e a segunda so apareceu ao tirar uma captura de
   ecra:

   - **Nao se esconde nada se a pagina ja abriu escondida.** Nesse caso o
     guiao sai e a pagina fica como o CSS a deixou, quieta e legivel.
   - **Se o separador perder o foco a meio, a animacao e parada e os estilos
     limpos.** Nao basta limpar: o anime.js volta a escrever a opacidade no
     frame seguinte e o elemento fica preso no valor onde o motor parou. Foi
     o que aconteceu - o logotipo da entrada ficou em `opacity: 0.21` e assim
     continuou. Quem limpa tem tambem de mandar parar.

   Por cima das duas fica um `setTimeout` de 1.2s, que continua a contar em
   separadores escondidos e serve onde o `requestAnimationFrame` nao serve.
2. **Quem pediu menos movimento nao leva nenhum.** `prefers-reduced-motion`
   e lido a entrada e o guiao sai sem tocar em nada.
3. **A animacao nao deixa residuo.** Ao acabar, os estilos que ela escreveu
   sao apagados; o elemento volta a ser governado pelo CSS.
4. **Curtas.** 200 a 420 ms. Isto e um motor de busca: o aluno veio buscar um
   ficheiro, nao ver uma abertura de filme. As cascatas levam passos de 22 ms
   - o suficiente para se ler como uma lista a chegar e nao a demorar.
"""

CAMINHO = "/estatico/anime.min.js"

# Ao fim disto os estilos da entrada sao limpos, tenha a animacao corrido ou
# nao. E a rede de seguranca da regra 1.
ESPERA_MAXIMA_MS = 1200

GUIAO = """
(function () {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arrancar);
  } else {
    arrancar();
  }

  function parado() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function arrancar() {
    // `defer` num <script> em linha nao faz nada - so vale para ficheiros de
    // fora. Sem a espera acima, isto corria antes de o anime.js carregar.
    if (parado() || typeof anime === "undefined") { return; }

    // Aberta ja escondida (ctrl+clique, sessao restaurada): nao se esconde
    // nada. O motor de animacao nao corre com o documento escondido, e uma
    // pagina a `opacity: 0` a espera dele fica em branco.
    if (document.hidden) { return; }

    var animar = anime.animate;
    var cascata = anime.stagger;
    var SAIDA = "outQuad";
    var porLimpar = [];

    /* Prepara, anima, e garante que os estilos escritos aqui desaparecem -
       porque a animacao acabou, porque o relogio disse que ja chega, ou
       porque o separador perdeu o foco. */
    function entrada(alvos, deslocamento, duracao, passo) {
      if (!alvos || !alvos.length) { return; }
      var limpo = false;
      var animacao = null;
      function limpar() {
        if (limpo) { return; }
        limpo = true;
        // Parar antes de limpar. Sem isto, o anime.js volta a escrever a
        // opacidade no frame seguinte e o elemento fica preso no valor onde
        // o motor parou.
        try { if (animacao) { animacao.pause(); } } catch (e) {}
        for (var i = 0; i < alvos.length; i++) {
          alvos[i].style.opacity = "";
          alvos[i].style.transform = "";
        }
      }
      porLimpar.push(limpar);
      anime.utils.set(alvos, { opacity: 0, translateY: deslocamento });
      setTimeout(limpar, __ESPERA__);
      animacao = animar(alvos, {
        opacity: 1,
        translateY: 0,
        duration: duracao,
        delay: cascata(passo),
        ease: SAIDA,
        onComplete: limpar,
      });
    }

    // Se o aluno mudar de separador a meio da entrada, o motor para onde
    // esta. Em vez de deixar meia pagina a meio gas, arruma-se tudo.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { return; }
      for (var i = 0; i < porLimpar.length; i++) { porLimpar[i](); }
    });

    function achar(seletor, raiz) {
      return (raiz || document).querySelectorAll(seletor);
    }

    // Os resultados sobem 10px e aparecem, um a seguir ao outro. O passo e
    // curto de proposito: com 60ms, dez resultados demoravam mais de meio
    // segundo a acabar de chegar e via-se a lista a escrever-se.
    entrada(achar(".resultado"), 10, 380, 22);

    // O heroi e a folha de entrada: cada peca entra por ordem de leitura.
    // O titulo grande e o que mais se nota, por isso vem cedo e sobe mais.
    var heroi = document.querySelector(".heroi-dentro, .entrada-caixa");
    if (heroi) {
      entrada(
        achar(".olho, .display, .lead, form.busca, .entrada-forma," +
              " .experimente, .nota-final", heroi),
        16, 460, 70
      );
    }

    entrada(achar(".abas .aba"), -6, 300, 28);
    entrada(achar(".metrica"), 8, 320, 26);
    entrada(achar(".lista-topo li"), 6, 260, 20);

    // As barras do grafico crescem do chao. `scaleY` a partir da base e mais
    // barato que animar a altura, que obrigaria a recalcular a disposicao a
    // cada frame.
    var barras = document.querySelectorAll(".grafico rect");
    if (barras.length) {
      anime.utils.set(barras, { transformOrigin: "50% 100%", scaleY: 0 });
      animar(barras, {
        scaleY: 1,
        duration: 620,
        delay: cascata(35),
        ease: "outCubic",
        onComplete: function () {
          for (var i = 0; i < barras.length; i++) {
            barras[i].style.transform = "";
          }
        },
      });
    }

    // O icone do tema roda meia volta ao trocar. Fica ligado ao clique e nao
    // ao estado: o estado ja e tratado no guiao do tema, e duas coisas a
    // escrever o mesmo atributo davam luta.
    var botaoTema = document.getElementById("botao-tema");
    if (botaoTema) {
      botaoTema.addEventListener("click", function () {
        animar(botaoTema, { rotate: [0, 180], duration: 420, ease: "outBack" });
      });
    }

    // As sugestoes sao refeitas a cada tecla. O observador dispara a animacao
    // sem que o codigo das sugestoes precise de saber que isto existe.
    var caixaSug = document.getElementById("sugestoes");
    if (caixaSug && window.MutationObserver) {
      new MutationObserver(function () {
        entrada(caixaSug.children, -4, 200, 14);
      }).observe(caixaSug, { childList: true });
    }

    // O painel de pre-visualizacao aparece depois de 350ms de rato parado
    // sobre um resultado. Sem entrada suave, saltava para o ecra.
    var painel = document.getElementById("painel");
    if (painel) {
      var visivel = false;
      new MutationObserver(function () {
        var aberto = painel.style.display === "block";
        if (aberto && !visivel) {
          animar(painel, {
            opacity: [0, 1],
            translateX: [-8, 0],
            duration: 260,
            ease: SAIDA,
          });
        }
        visivel = aberto;
      }).observe(painel, { attributes: true, attributeFilter: ["style"] });
    }
  }
})();
""".replace("__ESPERA__", str(ESPERA_MAXIMA_MS))


def marcacao() -> str:
    """O `<script>` da biblioteca mais o guiao, para o fim do `<body>`.

    A biblioteca leva `defer` - nao ha razao para segurar a pintura por causa
    dela. O guiao e em linha e espera pelo `DOMContentLoaded`, que corre
    depois dos `defer` todos.
    """
    return (
        f'<script src="{CAMINHO}" defer></script>\n'
        f"<script>{GUIAO}</script>"
    )
