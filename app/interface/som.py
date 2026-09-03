"""Os sons de interface, sintetizados no proprio browser.

**Nao ha ficheiros de audio.** Tudo o que se ouve e feito na hora pela Web
Audio API: um oscilador, um pouco de ruido filtrado, e um envelope de queda
muito rapido. Isto poupa os 40-80 KB que quatro ficheiros de som custariam, e
mantem a regra do projeto - nao se vai buscar nada a servidores alheios.

Quatro decisoes que valem a pena explicar:

1. **O contexto de audio so nasce ao primeiro clique.** Os browsers bloqueiam
   audio antes de haver um gesto do utilizador; criar o contexto no
   carregamento deixava-o em `suspended` e enchia a consola de avisos. Como
   estes sons sao todos disparados por cliques, o primeiro clique e o gesto
   que os autoriza.

2. **Um som so para tudo soa a brinquedo.** Sao quatro, e a diferenca entre
   eles e o que faz a interface parecer que responde em vez de apitar: o
   toque seco de um botao, o par ascendente de uma busca enviada, o estalido
   curto de navegar nas sugestoes, e um tom mais cheio ao abrir um documento.

3. **Um clique real nao e um "bip".** Um seno puro soa a electrodomestico. O
   que da a sensacao de clique e o transiente: um golpe de ruido de 8 ms
   passado por um filtro passa-banda, com um corpo de seno por baixo a
   desaparecer em 60 ms. E por isso que ha duas fontes e nao uma.

4. **Da para desligar, e fica desligado.** O botao esta ao lado do do tema e a
   escolha vai para o `localStorage`. Isto e usado numa sala de aula: uma
   turma inteira a clicar com som ligado seria insuportavel, e quem precisar
   de silencio tem de o conseguir a primeira tentativa.
"""

# Volume de base. Baixo de proposito: estes sons sao para se notarem sem se
# darem por eles. Acima de .1 ja se ouve na sala ao lado.
VOLUME = 0.05

GUIAO = """
(function () {
  var CHAVE = "som";
  var VOLUME = __VOLUME__;
  var ctx = null;

  function ligado() {
    try { return localStorage.getItem(CHAVE) !== "off"; } catch (e) { return true; }
  }

  // Sem gesto do utilizador o browser recusa o contexto; por isso ele so
  // nasce aqui, ja dentro do tratamento de um clique.
  function contexto() {
    if (ctx) { return ctx; }
    var Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) { return null; }
    try { ctx = new Audio(); } catch (e) { return null; }
    return ctx;
  }

  // Um golpe de ruido curto: e isto que da o "tique" de um clique, e nao o
  // tom. Sozinho soa a estatica; sob um seno, soa a botao.
  function transiente(c, agora, ganho, corte) {
    var amostras = Math.floor(c.sampleRate * 0.008);
    var buffer = c.createBuffer(1, amostras, c.sampleRate);
    var dados = buffer.getChannelData(0);
    for (var i = 0; i < amostras; i++) {
      dados[i] = (Math.random() * 2 - 1) * (1 - i / amostras);
    }
    var fonte = c.createBufferSource();
    fonte.buffer = buffer;
    var filtro = c.createBiquadFilter();
    filtro.type = "bandpass";
    filtro.frequency.value = corte;
    filtro.Q.value = 0.8;
    var vol = c.createGain();
    vol.gain.value = ganho;
    fonte.connect(filtro).connect(vol).connect(c.destination);
    fonte.start(agora);
  }

  function tom(c, agora, freq, duracao, ganho, forma) {
    var osc = c.createOscillator();
    osc.type = forma || "sine";
    osc.frequency.setValueAtTime(freq, agora);
    var vol = c.createGain();
    // Ataque de 1 ms e queda exponencial: o corte seco a zero estalava.
    vol.gain.setValueAtTime(0.0001, agora);
    vol.gain.exponentialRampToValueAtTime(ganho, agora + 0.001);
    vol.gain.exponentialRampToValueAtTime(0.0001, agora + duracao);
    osc.connect(vol).connect(c.destination);
    osc.start(agora);
    osc.stop(agora + duracao + 0.02);
  }

  function tocar(especie) {
    if (!ligado()) { return; }
    var c = contexto();
    if (!c) { return; }
    if (c.state === "suspended") { c.resume(); }
    var t = c.currentTime;
    var v = VOLUME;
    if (especie === "enviar") {
      // Par ascendente: le-se como "isto partiu".
      transiente(c, t, v * 0.5, 2000);
      tom(c, t, 520, 0.05, v * 0.7);
      tom(c, t + 0.045, 780, 0.07, v * 0.6);
    } else if (especie === "abrir") {
      // Mais cheio e mais grave: abriu-se alguma coisa.
      transiente(c, t, v * 0.4, 1400);
      tom(c, t, 340, 0.11, v * 0.85, "triangle");
    } else if (especie === "tique") {
      // Navegar nas sugestoes com as setas. Quase inaudivel de proposito:
      // dispara muitas vezes seguidas.
      transiente(c, t, v * 0.35, 3200);
    } else {
      // Clique comum.
      transiente(c, t, v * 0.6, 2400);
      tom(c, t, 440, 0.055, v * 0.55);
    }
  }

  window.somMadalena = tocar;

  // Um so ouvinte na raiz em vez de um por elemento: os resultados sao
  // refeitos a cada pagina e as sugestoes a cada tecla, e ligar ouvintes a
  // cada um deles obrigava a lembrar de os desligar.
  document.addEventListener("click", function (e) {
    var alvo = e.target.closest(
      "a, button, .aba, .paginacao a, .temas .tema, .experimente a"
    );
    if (!alvo || alvo.id === "botao-som") { return; }
    if (alvo.matches("button[type=submit], .botao-entrar")) { tocar("enviar"); }
    else if (alvo.matches(".titulo a, ul.novo-lista a, ul.dsc a")) { tocar("abrir"); }
    else { tocar("clique"); }
  }, true);

  document.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") { return; }
    var caixa = document.getElementById("sugestoes");
    if (caixa && caixa.style.display === "block") { tocar("tique"); }
  }, true);

  var botao = document.getElementById("botao-som");
  if (!botao) { return; }
  var ligadoIc = botao.querySelector(".ic-som");
  var mudoIc = botao.querySelector(".ic-mudo");
  function rotular() {
    var on = ligado();
    if (ligadoIc) { ligadoIc.style.display = on ? "" : "none"; }
    if (mudoIc) { mudoIc.style.display = on ? "none" : ""; }
    var diz = on ? "Desligar o som" : "Ligar o som";
    botao.setAttribute("aria-label", diz);
    botao.setAttribute("title", diz);
    botao.setAttribute("aria-pressed", on ? "true" : "false");
  }
  botao.addEventListener("click", function () {
    var novo = ligado() ? "off" : "on";
    try { localStorage.setItem(CHAVE, novo); } catch (e) {}
    rotular();
    // Toca uma vez ao ligar, para se ouvir o que se acabou de escolher.
    if (novo === "on") { tocar("clique"); }
  });
  rotular();
})();
""".replace("__VOLUME__", str(VOLUME))


def botao() -> str:
    """O botao de ligar/desligar, com os dois icones dentro.

    O mesmo padrao do botao do tema: os dois desenhos vivem no HTML e o guiao
    esconde o que nao serve, para o SVG nao ter de existir tambem em
    JavaScript.
    """
    from app.interface import icones

    return (
        '<button type="button" class="icone-botao" id="botao-som" '
        'aria-label="ligar ou desligar o som">'
        f'<span class="ic-som">{icones.svg("som", 16)}</span>'
        f'<span class="ic-mudo">{icones.svg("sem-som", 16)}</span>'
        "</button>"
    )


def marcacao() -> str:
    return f"<script>{GUIAO}</script>"
