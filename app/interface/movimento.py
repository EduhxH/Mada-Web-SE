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

   A defesa e o relogio de seguranca: ao fim de 1.2s os estilos da entrada
   sao apagados, tenha a animacao corrido ou nao. O `setTimeout` continua a
   contar em separadores escondidos - so fica mais lento - e por isso serve
   onde o `requestAnimationFrame` nao serve.
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

    var animar = anime.animate;
    var cascata = anime.stagger;
    var SAIDA = "outQuad";

    /* Prepara, anima, e garante que os estilos escritos aqui desaparecem -
       ou porque a animacao acabou, ou porque o relogio disse que ja chega. */
    function entrada(alvos, deslocamento, duracao, passo) {
      if (!alvos || !alvos.length) { return; }
      var limpo = false;
      function limpar() {
        if (limpo) { return; }
        limpo = true;
        for (var i = 0; i < alvos.length; i++) {
          alvos[i].style.opacity = "";
          alvos[i].style.transform = "";
        }
      }
      anime.utils.set(alvos, { opacity: 0, translateY: deslocamento });
      setTimeout(limpar, __ESPERA__);
      animar(alvos, {
        opacity: 1,
        translateY: 0,
        duration: duracao,
        delay: cascata(passo),
        ease: SAIDA,
        onComplete: limpar,
      });
    }

    function achar(seletor, raiz) {
      return (raiz || document).querySelectorAll(seletor);
    }

    // Os resultados sobem 10px e aparecem, um a seguir ao outro. O passo e
    // curto de proposito: com 60ms, dez resultados demoravam mais de meio
    // segundo a acabar de chegar e via-se a lista a escrever-se.
    entrada(achar(".resultado"), 10, 380, 22);

    // A entrada e a pagina de codigo: marca, lema, caixa, por esta ordem.
    var centro = document.querySelector(".centro");
    if (centro) {
      entrada(
        achar(
          ".marca-grande, .lema, .sublema, form.busca, .cartao-entrada," +
          " .aviso, .abaixo",
          centro
        ),
        12, 420, 60
      );
    }

    entrada(achar(".abas .aba"), -6, 300, 28);

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
