"""A marcacao da newsletter, e sobretudo o que ela recusa.

Isto e a unica parte do projeto onde texto escrito por uma pessoa se transforma
em HTML que outra pessoa recebe. A defesa e a ordem das operacoes - escapar
tudo antes de interpretar seja o que for - e os testes que interessam sao os
negativos: o que **nao** pode sair daqui.
"""

from html.parser import HTMLParser

import pytest

from app.interface import marcacao

# As unicas etiquetas que este renderizador tem direito a produzir. Tudo o resto
# que apareca no resultado veio do texto de alguem, e nao devia ter chegado la.
ETIQUETAS_PERMITIDAS = {
    "p", "strong", "em", "code", "a", "img", "video", "figure",
    "h2", "h3", "ul", "ol", "li", "blockquote", "hr",
}
ESQUEMAS_PERMITIDOS = ("https://", "http://", "/")


class _Inspector(HTMLParser):
    """Le a saida como um browser a leria, e aponta o que nao devia la estar.

    Procurar substrings no resultado nao serve: `&lt;img src=x onerror=...&gt;`
    contem "onerror=" e e texto inerte, e um teste que o reprovasse estaria a
    gritar pelo motivo errado - o que e pior do que nao gritar, porque ensina a
    ignora-lo. Aqui so conta o que o parser reconhece como etiqueta.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.queixas: list[str] = []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta not in ETIQUETAS_PERMITIDAS:
            self.queixas.append(f"etiqueta inesperada: <{etiqueta}>")
        for nome, valor in atributos:
            if nome.lower().startswith("on"):
                self.queixas.append(f"atributo de evento: {nome}")
            if nome.lower() in ("href", "src") and valor is not None:
                if not valor.lower().startswith(ESQUEMAS_PERMITIDOS):
                    self.queixas.append(f"{nome} com esquema recusado: {valor}")

    handle_startendtag = handle_starttag


def queixas_de(fonte: str) -> list[str]:
    inspector = _Inspector()
    inspector.feed(marcacao.para_html(fonte))
    inspector.close()
    return inspector.queixas


# --------------------------------------------------------------- o que sai


def test_paragrafo_simples():
    assert marcacao.para_html("olá turma") == "<p>olá turma</p>"


def test_enfases():
    saida = marcacao.para_html("**forte** e *torto* e `código`")
    assert "<strong>forte</strong>" in saida
    assert "<em>torto</em>" in saida
    assert "<code>código</code>" in saida


def test_negrito_ganha_ao_italico():
    """`**x**` tem de virar forte e nao um italico dentro de asteriscos."""
    saida = marcacao.para_html("**x**")
    assert saida == "<p><strong>x</strong></p>"


def test_titulos_listas_citacao_e_linha():
    fonte = "## Dois\n\n### Três\n\n- um\n- dois\n\n1. a\n2. b\n\n> citado\n\n---"
    saida = marcacao.para_html(fonte)
    assert '<h2 class="nl-titulo">Dois</h2>' in saida
    assert '<h3 class="nl-titulo">Três</h3>' in saida
    assert "<ul><li>um</li><li>dois</li></ul>" in saida
    assert "<ol><li>a</li><li>b</li></ol>" in saida
    assert "<blockquote>citado</blockquote>" in saida
    assert '<hr class="nl-linha">' in saida


def test_citacao_funciona_apesar_de_o_escape_correr_primeiro():
    """O `>` da citacao ja e `&gt;` quando as regras de bloco correm.

    Foi assim que este bug apareceu: a marcacao e aplicada depois do escape, de
    proposito, e o padrao da citacao procurava um `>` que ja nao existia.
    """
    assert "<blockquote>" in marcacao.para_html("> citado")
    # Quem escreve literalmente "&gt;" quer ver "&gt;" e nao uma citacao: o
    # escape transforma o `&` desse texto em `&amp;`, e o padrao nao casa.
    assert "<blockquote>" not in marcacao.para_html("&gt; citado")


def test_linhas_seguidas_juntam_se_num_paragrafo():
    saida = marcacao.para_html("uma linha\noutra linha\n\nnovo bloco")
    assert saida == "<p>uma linha outra linha</p><p>novo bloco</p>"


def test_ligacao_interna_nao_abre_noutro_separador():
    saida = marcacao.para_html("[busca](/?q=pap)")
    assert 'href="/?q=pap"' in saida
    assert "target=" not in saida


def test_ligacao_externa_leva_noopener():
    saida = marcacao.para_html("[Moodle](https://moodle.sefo.pt/x?a=1&b=2)")
    assert 'rel="noopener noreferrer"' in saida
    assert 'target="_blank"' in saida
    # O `&` do endereco chega aqui ja escapado, e e assim que tem de ficar.
    assert "a=1&amp;b=2" in saida


def test_imagem_e_video_locais():
    assert '<img class="nl-img" src="/media/abc.png"' in marcacao.para_html(
        "![gato](/media/abc.png)"
    )
    assert '<video class="nl-video"' in marcacao.para_html("!video(/media/a.mp4)")


def test_imagem_sozinha_na_linha_vira_figura():
    assert marcacao.para_html("![](/media/a.png)").startswith("<figure>")
    assert "<figure>" not in marcacao.para_html("texto ![](/media/a.png) mais")


# ------------------------------------------------------------ o que recusa


@pytest.mark.parametrize(
    "ataque",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "<iframe src=//mau></iframe>",
        "<svg onload=alert(1)>",
        "<body onload=alert(1)>",
        "'\"><script>alert(1)</script>",
        "[a](javascript:alert(1))",
        "[a](JaVaScRiPt:alert(1))",
        "[a](&#106;avascript:alert(1))",
        "[a](&#x6a;avascript:alert(1))",
        "![a](javascript:alert(1))",
        "![a](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
        "!video(javascript:alert(1))",
        "## <script>alert(1)</script>",
        "> <script>alert(1)</script>",
        "- <script>alert(1)</script>",
        "**<script>alert(1)</script>**",
        "`<script>alert(1)</script>`",
    ],
)
def test_nada_disto_vira_html(ataque):
    queixas = queixas_de(ataque)
    assert not queixas, f"{queixas} em {marcacao.para_html(ataque)!r}"


def test_entidade_codificada_e_desfeita_antes_de_validar():
    """`&#106;avascript:` e `javascript:` depois de o browser o ler.

    Validar a forma escapada seria validar uma coisa e navegar outra.
    """
    saida = marcacao.para_html("[a](&#106;avascript:alert(1))")
    assert "<a " not in saida


@pytest.mark.parametrize(
    "endereco",
    [
        "https://exemplo.pt/foto.png",
        "http://exemplo.pt/foto.gif",
        "//exemplo.pt/foto.png",
        "/etc/passwd",
        "/media/../../.env",
        "/media/a b.png",
        "ftp://exemplo.pt/x.png",
    ],
)
def test_media_so_pode_vir_desta_maquina(endereco):
    """Uma imagem alojada fora e o endereco de cada aluno entregue a terceiros."""
    saida = marcacao.para_html(f"![x]({endereco})")
    assert "<img" not in saida
    assert not queixas_de(f"![x]({endereco})")


def test_video_de_fora_recusado():
    assert "recusado" in marcacao.para_html("!video(https://exemplo.pt/x.mp4)")


def test_o_inspector_apanharia_mesmo(monkeypatch):
    """O teste do teste: um renderizador estragado tem de reprovar.

    Um verificador que nunca falha nao esta a verificar nada, e isso so se sabe
    partindo-o de proposito.
    """
    monkeypatch.setattr(
        marcacao, "para_html", lambda corpo: '<a href="javascript:x">m</a><script>y</script>'
    )
    assert len(queixas_de("seja o que for")) == 2


def test_corpo_gigante_e_cortado():
    saida = marcacao.para_html("a" * (marcacao.LIMITE_CORPO + 5000))
    assert len(saida) < marcacao.LIMITE_CORPO + 100


def test_corpo_vazio():
    assert marcacao.para_html("") == ""
    assert marcacao.para_html(None) == ""


# ------------------------------------------------------------------ resumo


def test_resumo_tira_a_marcacao_e_guarda_a_frase():
    resumo = marcacao.resumir(
        "## Título\n\n- **Física-Química** e pré-aula\n\n[Moodle](/a) no fim"
    )
    assert resumo == "Título Física-Química e pré-aula Moodle no fim"


def test_resumo_nao_parte_palavras_com_hifen():
    """Comer todos os hifenes fazia de "Fisica-Quimica" duas palavras."""
    assert "Física-Química" in marcacao.resumir("- Física-Química")


def test_resumo_corta_no_espaco_e_poe_reticencias():
    resumo = marcacao.resumir("palavra " * 60, limite=40)
    assert len(resumo) <= 40
    assert resumo.endswith("…")
