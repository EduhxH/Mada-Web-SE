"""O painel de administracao: estatisticas, utilizadores, registo, operacoes, newsletter.

Seis secoes atras da mesma barreira, com uma condicao a mais do que o resto do
site: e preciso ser administrador. `/estatisticas` era visivel a todos os
participantes com as consultas de uma pessoa so escondidas; passou a ser daqui, e
daqui so entra quem tem um codigo `admin-`.

**Server-rendered, como tudo o mais.** Nao ha aplicacao de pagina unica: cada
secao e um endereco que se pode marcar nos favoritos, recarregar e abrir num
separador novo. O JavaScript acrescenta as tres coisas que sao impossiveis sem
ele - a consola ao vivo, o estado das operacoes enquanto correm, e a
pre-visualizacao do post - e nada mais depende dele.

**A pre-visualizacao e feita pelo servidor.** O editor manda o texto a
`/painel/api/previa` e recebe o HTML de volta. Parece um desvio, e e de
proposito: escrever um segundo renderizador em JavaScript seria ter duas
definicoes do que a marcacao significa, e a que interessa - a que decide o que
e seguro mostrar - e a de Python. Assim o que se ve no editor e literalmente o
que o aluno vai ver.

**Tudo o que entra e escapado, tudo o que sai por JSON e posto com textContent.**
As linhas de registo levam consigo o que as pessoas pesquisaram, e uma consulta
pode ser qualquer texto: e a unica entrada do painel que nao veio de mim.
"""

import html
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.analytics import uso
from app.crawler import horarios
from app.indexing import storage
from app.interface import (
    avisos,
    estatisticas,
    estilo,
    estilo_painel,
    icones,
    marcacao,
    media,
    operacoes,
    presenca,
    som,
)
from app.models import newsletter, novidades

CAMINHO_BANCO = Path("data") / "indice.sqlite3"

VISAO = "visao"
UTILIZADORES = "utilizadores"
REGISTO = "registo"
AUTOMATIZACAO = "automatizacao"
NEWSLETTER = "newsletter"
PERFIL = "perfil"

SECCOES: tuple[tuple[str, str, str], ...] = (
    (VISAO, "Visão geral", "painel"),
    (UTILIZADORES, "Utilizadores", "pessoas"),
    (REGISTO, "Registo", "terminal"),
    (AUTOMATIZACAO, "Automatização", "engrenagem"),
    (NEWSLETTER, "Newsletter", "jornal"),
    (PERFIL, "Perfil", "pessoa"),
)
CHAVES = tuple(chave for chave, _, _ in SECCOES)

_ICONE_APARELHO = {
    presenca.TELEMOVEL: "telemovel",
    presenca.TABLET: "tablet",
    presenca.COMPUTADOR: "computador",
    presenca.DESCONHECIDO: "globo",
}

# O que cada tipo de evento quer dizer em portugues, para a coluna "a fazer".
_ACCAO_LEGIVEL = {
    uso.EVENTO_BUSCA: "pesquisou",
    uso.EVENTO_ABERTURA: "abriu",
    uso.EVENTO_PREVIEW: "pré-viu",
    uso.EVENTO_SUGESTAO: "aceitou sugestão",
    uso.EVENTO_ENTRADA: "entrou",
}


# Recados de uma accao para a pagina seguinte, uma gaveta por administrador.
#
# Passa-los pelo endereco (`?ok=guardado`) seria mais simples, e foi a primeira
# ideia - mas um codigo de acesso novo tem de aparecer no ecra e um endereco vai
# para o historico do browser, para o registo de qualquer intermediario e para a
# barra que se mostra a sala inteira num projetor. Um codigo de acesso nao entra
# num URL. Ficando em memoria, e lido uma vez e desaparece.
_recados: dict[str, dict] = {}
_tranca_recados = threading.Lock()


def deixar_recado(
    participante: str,
    texto: str,
    mau: bool = False,
    codigos: list[tuple[str, str]] | None = None,
) -> None:
    with _tranca_recados:
        _recados[participante] = {
            "recado": texto,
            "recado_mau": mau,
            "codigos": codigos or [],
        }


def tirar_recado(participante: str) -> dict:
    """Le e apaga. Um recado mostra-se uma vez; recarregar a pagina nao o repete."""
    with _tranca_recados:
        return _recados.pop(participante, {})


def caminho_de(chave: str) -> str:
    return "/painel" if chave == VISAO else f"/painel/{chave}"


def _e(texto) -> str:
    return html.escape(str(texto if texto is not None else ""), quote=True)


# --------------------------------------------------------------- moldura


def _nav(ativa: str, contas: dict[str, int]) -> str:
    itens = []
    for chave, rotulo, icone in SECCOES:
        quantos = avisos.etiqueta(contas.get(chave, 0))
        ponto = f'<span class="pn-ponto">{quantos}</span>' if quantos else ""
        classe = " ativa" if chave == ativa else ""
        itens.append(
            f'<a class="{classe.strip() or ""}" href="{caminho_de(chave)}">'
            f'{icones.svg(icone, 16)}<span class="rotulo">{_e(rotulo)}</span>'
            f"{ponto}</a>"
        )
    return (
        '<nav class="pn-nav">'
        '<p class="olho">Administração</p>'
        f'<div class="pn-itens">{"".join(itens)}</div>'
        "</nav>"
    )


def _cabeca_secao(olho: str, titulo: str, lead: str = "") -> str:
    texto = f'<p class="lead">{lead}</p>' if lead else ""
    return (
        '<div class="pn-cabeca">'
        f'<p class="olho">{_e(olho)}</p>'
        f'<h1 class="display">{_e(titulo)}</h1>'
        f"{texto}</div>"
    )


def _recado(contexto: dict) -> str:
    texto = contexto.get("recado")
    if not texto:
        return ""
    mau = " mau" if contexto.get("recado_mau") else ""
    icone = "alerta" if contexto.get("recado_mau") else "visto"
    return (
        f'<p class="pn-recado{mau}">{icones.svg(icone, 15)}'
        f"<span>{_e(texto)}</span></p>"
    )


def pagina(
    seccao: str,
    participante: str,
    conexao,
    contexto: dict | None = None,
) -> str:
    """A pagina inteira de uma secao do painel."""
    contexto = contexto or {}
    if seccao not in CHAVES:
        seccao = VISAO
    try:
        contas = avisos.contar(conexao)
    except Exception:
        contas = {}
    # Abrir a secao apaga o seu proprio ponto. Marca-se depois de contar, senao
    # o ponto desaparecia antes de ser desenhado e nunca se via nada.
    avisos.marcar_visto(seccao, conexao)

    montadores = {
        VISAO: lambda: _visao(conexao, participante),
        UTILIZADORES: lambda: _utilizadores(conexao, participante, contexto),
        REGISTO: lambda: _registo(),
        AUTOMATIZACAO: lambda: _automatizacao(participante),
        NEWSLETTER: lambda: _newsletter(participante, contexto),
        PERFIL: lambda: _perfil(participante, contexto),
    }
    _, rotulo, _ = next(s for s in SECCOES if s[0] == seccao)
    corpo = montadores[seccao]()

    return (
        f"{estilo.cabeca(f'Madalena - {rotulo.lower()}', estilo_painel.CSS)}\n"
        "<body>\n"
        '<header class="topo"><div class="topo-linha">'
        f"{estilo.marca()}"
        f"{estilo.acoes('painel-' + seccao, True)}"
        "</div></header>\n"
        '<div class="pn"><div class="pn-grelha">'
        f"{_nav(seccao, contas)}"
        f'<main class="pn-corpo">{_recado(contexto)}{corpo}</main>'
        "</div></div>\n"
        '<footer class="rodape">'
        f"<span>Sessão de {_e(participante)}</span>"
        "<span>Dados pseudonimizados</span>"
        '<span><a href="/">Voltar à busca</a></span>'
        f"{estilo.credito()}"
        "</footer>\n"
        f"<script>{estilo.GUIAO_BOTAO_TEMA}</script>\n"
        f"<script>{GUIAO}</script>\n"
        f"{som.marcacao()}\n"
        "</body>\n</html>"
    )


# ---------------------------------------------------------- visao geral


def _linha_estado(rotulo: str, valor: str) -> str:
    return (
        f"<tr><td><span class=\"pn-rotulo\">{_e(rotulo)}</span></td>"
        f"<td>{_e(valor)}</td></tr>"
    )


def _quando_ficheiro(caminho: Path) -> str:
    try:
        marca = datetime.fromtimestamp(caminho.stat().st_mtime)
    except OSError:
        return "nunca"
    return marca.strftime("%Y-%m-%d %H:%M")


def _visao(conexao, participante: str) -> str:
    """Metricas de uso, mais o estado da maquina em quatro linhas.

    As metricas respondem "a turma esta a usar isto?". O estado responde "isto
    esta a funcionar?" - que e uma pergunta diferente e e a que se faz as sete
    da manha do dia da apresentacao.
    """
    corpo_estatisticas = estatisticas.corpo(conexao, administrador=True)

    documentos = disciplinas = 0
    if CAMINHO_BANCO.exists():
        try:
            with storage.emprestada(CAMINHO_BANCO) as indice:
                documentos = storage.contar_documentos(indice)
                disciplinas = storage.contar_disciplinas(indice)
        except Exception:
            pass

    try:
        presentes = uso.presencas(conexao)
    except Exception:
        presentes = {}
    online = sum(1 for p in presentes.values() if presenca.esta_online(p["visto"]))

    publicados, rascunhos = newsletter.contar()
    estado_horario = horarios.ler_estado()
    linhas = [
        _linha_estado(
            "índice",
            f"{documentos} documentos em {disciplinas} disciplinas"
            if documentos
            else "vazio - falta indexar",
        ),
        _linha_estado("última reindexação", _quando_ficheiro(CAMINHO_BANCO)),
        _linha_estado(
            "horário",
            f"apanhado em {estado_horario.get('ultima_mudanca', '')[:10]}"
            if estado_horario.get("ultima_mudanca")
            else "nunca apanhado",
        ),
        _linha_estado(
            "material novo",
            f"{novidades.contar_recentes()} nos últimos {novidades.DIAS_RECENTES} dias",
        ),
        _linha_estado(
            "newsletter", f"{publicados} publicados, {rascunhos} rascunhos"
        ),
        _linha_estado("agora online", f"{online} de {len(presentes)} conhecidos"),
    ]

    return (
        _cabeca_secao(
            "Visão geral",
            "Estatísticas",
            "Como a turma está a usar o motor, e se a máquina está de pé. "
            "Estes números são de quem usou, não de quem é: os rótulos são "
            "pseudónimos e não há nomes nem endereços em parte nenhuma.",
        )
        + f'<div class="pn-secao">{corpo_estatisticas}</div>'
        + '<section class="pn-secao">'
        '<p class="olho">Estado do sistema</p>'
        f'<div class="pn-rolo"><table class="pn-tabela">{"".join(linhas)}</table></div>'
        "</section>"
    )


# -------------------------------------------------------- utilizadores


def _selo_aparelho(aparelho: str | None) -> str:
    chave = aparelho or presenca.DESCONHECIDO
    icone = _ICONE_APARELHO.get(chave, "globo")
    return (
        f'<span class="pn-aparelho" title="{_e(chave)}">'
        f'{icones.svg(icone, 15)}<span>{_e(chave)}</span></span>'
    )


def _a_fazer(evento: dict | None, pagina_atual: str | None) -> str:
    """Uma frase curta sobre o que a pessoa fez por ultimo.

    Sai do registo de eventos e nao da tabela de presenca: o texto de uma
    consulta tem prazo de validade e vive num sitio so.
    """
    if not evento:
        return f"em /{pagina_atual}" if pagina_atual else "—"
    verbo = _ACCAO_LEGIVEL.get(evento.get("tipo", ""), evento.get("tipo", ""))
    consulta = (evento.get("consulta") or "").strip()
    if consulta:
        return f'{verbo} "{consulta}"'
    if evento.get("doc_id"):
        return f"{verbo} o documento {evento['doc_id']}"
    return verbo


def _utilizadores(conexao, participante: str, contexto: dict) -> str:
    from app.interface import auth

    participantes = sorted(set(auth.carregar_participantes().values()))
    try:
        presentes = uso.presencas(conexao)
        ultimos = uso.ultimos_eventos(conexao)
    except Exception:
        presentes, ultimos = {}, {}

    agora = datetime.now(timezone.utc)
    simbolo = auth.simbolo_csrf(participante)
    linhas = []
    for rotulo in participantes:
        marca = presentes.get(rotulo, {})
        idade = presenca.segundos_desde(marca.get("visto"), agora)
        online = presenca.esta_online(marca.get("visto"), agora)
        eu = rotulo == participante
        papel = (
            '<span class="pn-papel">admin</span>'
            if auth.e_administrador(rotulo)
            else ""
        )
        retrato = media.perfil_de(rotulo)
        cara = (
            f'<img class="nl-retrato" src="/perfil/{_e(retrato)}" alt="">'
            if retrato
            else ""
        )
        acoes = [
            f'<form method="post" action="/painel/utilizadores">'
            f'<input type="hidden" name="csrf" value="{simbolo}">'
            f'<input type="hidden" name="rotulo" value="{_e(rotulo)}">'
            f'<input type="hidden" name="accao" value="novo-codigo">'
            f'<button class="pn-botao" type="submit" '
            f'title="gera um código novo e fecha a sessão aberta">'
            f'{icones.svg("chave", 14)}novo código</button></form>'
        ]
        if eu:
            # Revogar-se a si mesmo deixava o painel sem ninguem que o abrisse, e
            # a unica saida era a linha de comandos. O botao nao existe.
            acoes.append(
                '<span class="pn-botao" aria-disabled="true" '
                'title="não te podes revogar a ti mesmo" '
                'style="opacity:.4;cursor:not-allowed">'
                f'{icones.svg("proibido", 14)}revogar</span>'
            )
        else:
            acoes.append(
                f'<form method="post" action="/painel/utilizadores" '
                f'data-confirmar="Revogar {_e(rotulo)}? O código deixa de '
                f'funcionar e a sessão fecha-se.">'
                f'<input type="hidden" name="csrf" value="{simbolo}">'
                f'<input type="hidden" name="rotulo" value="{_e(rotulo)}">'
                f'<input type="hidden" name="accao" value="revogar">'
                f'<button class="pn-botao perigo" type="submit">'
                f'{icones.svg("proibido", 14)}revogar</button></form>'
            )
        linhas.append(
            f'<tr data-quem="{_e(rotulo)}">'
            f'<td><div class="pn-quem">{cara}'
            f'<span class="pn-rotulo">{_e(rotulo)}</span>{papel}</div></td>'
            f'<td><span class="pn-estado">'
            f'<span class="pn-bolha{" online" if online else ""}"></span>'
            f'<span class="palavra">{"online" if online else "offline"}</span>'
            "</span></td>"
            f'<td class="visto">{_e(presenca.ha_quanto_tempo(idade))}</td>'
            f'<td>{_selo_aparelho(marca.get("dispositivo"))}</td>'
            f'<td><span class="pn-faz">'
            f'{_e(_a_fazer(ultimos.get(rotulo), marca.get("pagina")))}</span></td>'
            f'<td class="acoes-celula"><div class="pn-acoes">{"".join(acoes)}</div></td>'
            "</tr>"
        )

    tabela = (
        '<div class="pn-rolo"><table class="pn-tabela">'
        "<thead><tr><th>participante</th><th>estado</th><th>visto</th>"
        "<th>aparelho</th><th>último passo</th><th></th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody></table></div>"
        if linhas
        else '<p class="pn-vazio">Nenhum participante. Cria o primeiro abaixo.</p>'
    )

    pendentes = contexto.get("codigos") or []
    if pendentes:
        linhas_codigo = "".join(
            f"<div><strong>{_e(rotulo)}</strong> &middot; <code>{_e(codigo)}</code></div>"
            for codigo, rotulo in pendentes
        )
        mostrado = (
            f'<div class="pn-recado">{icones.svg("chave", 15)}<div>'
            "<div>Copia agora — não voltam a aparecer. No disco fica só o "
            "HMAC de cada um.</div>"
            f"{linhas_codigo}</div></div>"
        )
    else:
        mostrado = ""

    criar = (
        '<section class="pn-secao">'
        '<p class="olho">Criar participantes</p>'
        '<div class="pn-cartao">'
        '<form method="post" action="/painel/utilizadores" class="pn-acoes">'
        f'<input type="hidden" name="csrf" value="{simbolo}">'
        '<input type="hidden" name="accao" value="criar">'
        '<label class="pn-campo" style="margin:0">'
        "<span>quantos</span>"
        '<input type="text" name="quantos" value="1" inputmode="numeric" '
        'style="width:86px" pattern="[0-9]{1,2}"></label>'
        '<label class="pn-campo" style="margin:0"><span>papel</span>'
        '<select name="papel" style="height:44px">'
        '<option value="aluno">aluno</option>'
        '<option value="admin">admin</option>'
        "</select></label>"
        f'<button class="pn-botao forte" type="submit">'
        f'{icones.svg("mais", 14)}criar</button>'
        "</form>"
        '<p class="pn-nota">Os códigos aparecem <strong>uma vez</strong>. No '
        "disco fica só o HMAC-SHA256 de cada um, portanto não há como os "
        "recuperar depois — só revogar e criar outro.</p>"
        "</div></section>"
    )

    return (
        _cabeca_secao(
            "Gestão",
            "Utilizadores",
            "Quem tem código, quem está a usar agora e de que aparelho. "
            f"Conta-se como online quem fez um pedido nos últimos "
            f"{uso.SEGUNDOS_ONLINE // 60} minutos — quem está a ler um PDF não "
            "faz pedidos e continua cá.",
        )
        + mostrado
        + f'<section class="pn-secao" data-vivo="presenca">{tabela}</section>'
        + criar
    )


# --------------------------------------------------------------- registo


def linha_registo(linha: dict) -> str:
    """Uma linha de registo em HTML. Escapada: o texto pode ser uma consulta."""
    return (
        f'<div class="ln {_e(linha["nivel"])}">'
        f'<span class="hora">{_e(linha["momento"][11:])}</span>'
        f'<span class="nivel">{_e(linha["origem"])}</span>'
        f'<span class="texto">{_e(linha["texto"])}</span>'
        "</div>"
    )


def _consola(origem: str = "", altura_cheia: bool = True) -> str:
    from app.interface import registo as registo_servidor

    linhas, ultimo = registo_servidor.desde(0, 200)
    if origem:
        alvos = set(origem.split(","))
        linhas = [l for l in linhas if l["origem"] in alvos]
    corpo = "".join(linha_registo(l) for l in linhas)
    if not corpo:
        corpo = (
            '<div class="ln"><span class="hora"></span>'
            '<span class="nivel"></span>'
            '<span class="texto">Nada registado ainda.</span></div>'
        )
    return (
        '<div class="pn-barra-consola">'
        '<span class="pn-viva ligada" id="pulso"><span class="bat"></span>'
        "<span>ao vivo</span></span>"
        '<label><input type="checkbox" id="seguir" checked> seguir o fim</label>'
        '<label><input type="checkbox" id="so-graves"> só avisos e erros</label>'
        "</div>"
        f'<div class="pn-consola" id="consola" data-desde="{ultimo}" '
        f'data-origem="{_e(origem)}">{corpo}</div>'
    )


def _registo() -> str:
    from app.interface import registo as registo_servidor

    return (
        _cabeca_secao(
            "Diagnóstico",
            "Registo do servidor",
            "Os pedidos, os avisos e os estouros, à medida que acontecem. "
            "Antes disto o servidor engolia tudo em silêncio e um erro no meio "
            "de uma aula não deixava rasto nenhum.",
        )
        + f'<section class="pn-secao">{_consola()}</section>'
        + '<p class="pn-nota">Fica em memória e morre com o processo — as linhas '
        "de pedido levam consigo o que foi pesquisado, e isso não tem razão para "
        "ficar em disco sem prazo. <strong>Avisos e erros</strong> são a exceção: "
        f"esses ficam em <code>{_e(registo_servidor.CAMINHO_DISCO)}</code>, que é "
        "onde se vai ver porque é que o servidor morreu.</p>"
    )


# --------------------------------------------------------- automatizacao


def _cartao_operacao(nome: str, participante: str, ocupado: str | None) -> str:
    from app.interface import auth

    estado = operacoes.estado(nome).como_json()
    if estado["a_correr"]:
        selo = f'<span class="pn-selo">{icones.svg("atualizar", 12)}a correr</span>'
    elif estado["bem"] is True:
        selo = f'<span class="pn-selo">{icones.svg("visto", 12)}correu bem</span>'
    elif estado["bem"] is False:
        selo = f'<span class="pn-selo mau">{icones.svg("alerta", 12)}falhou</span>'
    else:
        selo = '<span class="pn-selo">nunca corrida aqui</span>'

    quando = (
        f"começou às {estado['comecou'][11:]}"
        if estado["a_correr"]
        else (
            f"última vez às {estado['terminou'][11:]} de "
            f"{estado['terminou'][:10]} ({estado['segundos']:.0f}s)"
            if estado["terminou"]
            else "sem registo nesta sessão do servidor"
        )
    )
    desativado = " disabled" if ocupado else ""
    return (
        f'<div class="pn-cartao pn-op" data-operacao="{_e(nome)}">'
        f"<h3>{_e(estado['rotulo'])}</h3>"
        f'<p class="quando">{_e(quando)}</p>'
        f'<p class="resultado">{selo} <span class="resumo">'
        f"{_e(estado['resumo'] or '—')}</span></p>"
        f'<div class="pn-acoes">'
        f'<form method="post" action="/painel/automatizacao">'
        f'<input type="hidden" name="csrf" value="{auth.simbolo_csrf(participante)}">'
        f'<input type="hidden" name="accao" value="{_e(nome)}">'
        f'<button class="pn-botao forte" type="submit"{desativado}>'
        f'{icones.svg("tocar", 14)}correr agora</button></form>'
        "</div></div>"
    )


def _automatizacao(participante: str) -> str:
    ocupado = operacoes.ocupado()
    cartoes = "".join(
        _cartao_operacao(nome, participante, ocupado) for nome in operacoes.NOMES
    )
    nota_ocupado = (
        f'<p class="pn-recado">{icones.svg("relogio", 15)}<span>'
        f"<strong>{_e(operacoes.NOMES[ocupado])}</strong> está a correr. "
        "Os botões voltam quando terminar — duas verificações ao mesmo tempo "
        "entrariam duas vezes no Moodle e reindexariam o mesmo corpus em "
        "paralelo.</span></p>"
        if ocupado
        else ""
    )
    return (
        _cabeca_secao(
            "Manutenção",
            "Automatização",
            "O agendador já faz isto três vezes por dia. Estes botões são para "
            "quando não se quer esperar — um professor publica a ficha no meio "
            "da aula e o material vem agora.",
        )
        + nota_ocupado
        + f'<section class="pn-secao" data-vivo="operacoes">'
        f'<div class="pn-operacoes">{cartoes}</div></section>'
        + '<section class="pn-secao"><p class="olho">O que a operação está a dizer</p>'
        f"{_consola('conteudos,horario')}</section>"
        + '<p class="pn-nota">Reindexar são cerca de dois minutos, por isso só '
        "acontece quando entrou material novo. Verificar é uma página por "
        "disciplina: catorze pedidos, catorze segundos.</p>"
    )


# ------------------------------------------------------------ newsletter


def _lista_posts(participante: str) -> str:
    from app.interface import auth

    posts = newsletter.listar()
    if not posts:
        return (
            '<p class="pn-vazio">Ainda não há posts. O primeiro que publicares '
            "aparece em <code>/novidades</code> para a turma toda.</p>"
        )
    simbolo = auth.simbolo_csrf(participante)
    itens = []
    for post in posts:
        estado = (
            '<span class="rascunho">rascunho</span>'
            if not post.publicado
            else "publicado"
        )
        alternar = "despublicar" if post.publicado else "publicar"
        itens.append(
            "<li>"
            '<div class="principal">'
            f'<h3><a href="/painel/newsletter?id={post.id}">'
            f"{_e(post.titulo or 'sem título')}</a></h3>"
            f'<p class="resumo">{_e(marcacao.resumir(post.corpo, 150))}</p>'
            f'<p class="meta"><span>{_e(post.data_curta)}</span>'
            f"<span>{_e(post.autor)}</span>{estado}</p>"
            "</div>"
            '<div class="pn-acoes">'
            f'<a class="pn-botao" href="/painel/newsletter?id={post.id}">'
            f'{icones.svg("ficheiro", 14)}editar</a>'
            f'<form method="post" action="/painel/newsletter">'
            f'<input type="hidden" name="csrf" value="{simbolo}">'
            f'<input type="hidden" name="id" value="{post.id}">'
            f'<input type="hidden" name="accao" value="{alternar}">'
            f'<button class="pn-botao" type="submit">'
            f'{icones.svg("olho" if not post.publicado else "proibido", 14)}'
            f"{alternar}</button></form>"
            f'<form method="post" action="/painel/newsletter" '
            f'data-confirmar="Apagar &quot;{_e(post.titulo or "sem título")}&quot;? '
            f'Não há volta.">'
            f'<input type="hidden" name="csrf" value="{simbolo}">'
            f'<input type="hidden" name="id" value="{post.id}">'
            f'<input type="hidden" name="accao" value="apagar">'
            f'<button class="pn-botao perigo" type="submit">'
            f'{icones.svg("lixo", 14)}apagar</button></form>'
            "</div></li>"
        )
    return f'<ul class="pn-lista-posts">{"".join(itens)}</ul>'


def _biblioteca(participante: str) -> str:
    from app.interface import auth

    ficheiros = media.listar()
    simbolo = auth.simbolo_csrf(participante)
    if not ficheiros:
        grelha = (
            '<p class="pn-vazio">Nada carregado ainda. Usa o campo acima: '
            f"{', '.join(sorted(media.EXTENSOES_IMAGEM + media.EXTENSOES_VIDEO))}.</p>"
        )
    else:
        cartoes = []
        for item in ficheiros:
            pre = (
                f'<video src="{_e(item["url"])}" muted preload="metadata"></video>'
                if item["familia"] == media.VIDEO
                else f'<img src="{_e(item["url"])}" alt="" loading="lazy">'
            )
            cartoes.append(
                "<figure>"
                f"{pre}"
                "<figcaption>"
                f'<input class="cod" readonly value="{_e(media.marcacao_de(item["nome"]))}" '
                'onclick="this.select()">'
                f'<span>{_e(media.legivel(item["bytes"]))}</span>'
                '<div class="pn-acoes">'
                f'<button class="pn-botao" type="button" data-inserir='
                f'"{_e(media.marcacao_de(item["nome"]))}">'
                f'{icones.svg("mais", 13)}inserir</button>'
                f'<form method="post" action="/painel/newsletter" '
                f'data-confirmar="Apagar este ficheiro? Os posts que o usam ficam '
                f'com um espaço vazio.">'
                f'<input type="hidden" name="csrf" value="{simbolo}">'
                f'<input type="hidden" name="accao" value="apagar-media">'
                f'<input type="hidden" name="nome" value="{_e(item["nome"])}">'
                f'<button class="pn-botao perigo" type="submit">'
                f'{icones.svg("lixo", 13)}</button></form>'
                "</div></figcaption></figure>"
            )
        grelha = f'<div class="pn-media">{"".join(cartoes)}</div>'
    return (
        '<section class="pn-secao">'
        '<div class="pn-linha-titulo"><p class="olho">Biblioteca</p></div>'
        f"{grelha}"
        '<p class="pn-nota">As imagens e os vídeos vêm <strong>desta máquina</strong>. '
        "Uma imagem alojada fora seria um pedido do browser de cada aluno a um "
        "servidor de terceiros cada vez que abrisse a newsletter — ou seja, o "
        "endereço da turma entregue a alguém. Ligações para fora são outra coisa "
        "e essas valem.</p>"
        "</section>"
    )


_FERRAMENTAS = (
    ("**", "**", "B", "negrito"),
    ("*", "*", "I", "itálico"),
    ("## ", "", "H2", "título"),
    ("- ", "", "•", "lista"),
    ("> ", "", chr(34), "citação"),
    ("[", "](https://)", "ligacao", "ligação"),
)


def _editor(post, participante: str) -> str:
    from app.interface import auth

    novo = post is None
    identificador = "" if novo else str(post.id)
    titulo = "" if novo else post.titulo
    corpo = "" if novo else post.corpo
    publicado = False if novo else post.publicado
    simbolo = auth.simbolo_csrf(participante)

    botoes = []
    for antes, depois, rotulo, dica in _FERRAMENTAS:
        visivel = icones.svg(rotulo, 13) if icones.existe(rotulo) else _e(rotulo)
        botoes.append(
            f'<button type="button" title="{_e(dica)}" '
            f'data-antes="{_e(antes)}" data-depois="{_e(depois)}">{visivel}</button>'
        )

    estado = (
        '<span class="pn-selo">publicado</span>'
        if publicado
        else '<span class="pn-selo">rascunho</span>'
    )
    alternar = "despublicar" if publicado else "publicar"

    return (
        '<form method="post" action="/painel/newsletter" '
        'enctype="multipart/form-data" id="forma-post">'
        f'<input type="hidden" name="csrf" value="{simbolo}">'
        f'<input type="hidden" name="id" value="{_e(identificador)}">'
        '<div class="pn-editor">'
        "<div>"
        '<label class="pn-campo"><span>título</span>'
        f'<input type="text" name="titulo" value="{_e(titulo)}" '
        f'maxlength="{newsletter.LIMITE_TITULO}" '
        'placeholder="O que a turma vai ler primeiro"></label>'
        '<label class="pn-campo"><span>texto</span>'
        f'<span class="pn-ferramentas">{"".join(botoes)}</span>'
        f'<textarea name="corpo" id="corpo-post" '
        f'maxlength="{newsletter.LIMITE_CORPO}" '
        'placeholder="**negrito**, *itálico*, [texto](endereço), ## título, '
        '- lista, &gt; citação, --- linha">'
        f"{_e(corpo)}</textarea></label>"
        "</div>"
        "<div>"
        '<p class="olho">Pré-visualização</p>'
        f'<div class="pn-previa"><div class="nl-corpo" id="previa">'
        f"{marcacao.para_html(corpo)}</div></div>"
        '<label class="pn-campo" style="margin-top:16px">'
        "<span>juntar imagem, gif ou vídeo</span>"
        '<input type="file" name="media" data-limites=\''
        + _e(json.dumps(media.limites()))
        + '\' accept="'
        + ",".join(f".{e}" for e in media.EXTENSOES_IMAGEM + media.EXTENSOES_VIDEO)
        + '"></label>'
        '<button class="pn-botao" type="submit" name="accao" value="carregar">'
        f'{icones.svg("imagem", 14)}carregar e inserir</button>'
        '<p class="pn-nota">Guarda o texto primeiro e acrescenta a marcação no '
        "fim — nada do que escreveste se perde ao carregar o ficheiro.</p>"
        "</div></div>"
        '<div class="pn-acoes" style="margin-top:24px">'
        f'<button class="pn-botao forte" type="submit" name="accao" value="guardar">'
        f'{icones.svg("guardar", 14)}guardar</button>'
        f'<button class="pn-botao" type="submit" name="accao" value="{alternar}">'
        f'{icones.svg("olho", 14)}{alternar}</button>'
        f"{estado}"
        '<a class="pn-botao" href="/painel/newsletter">cancelar</a>'
        "</div></form>"
    )


def _newsletter(participante: str, contexto: dict) -> str:
    editando = contexto.get("post") is not None or contexto.get("novo")
    if editando:
        post = contexto.get("post")
        return (
            _cabeca_secao(
                "Newsletter",
                "Novo post" if post is None else "Editar post",
                "A pré-visualização é feita pelo servidor, com o mesmo "
                "renderizador que a turma vai ver — não é uma aproximação.",
            )
            + f'<section class="pn-secao">{_editor(post, participante)}</section>'
            + _biblioteca(participante)
        )

    publicados, rascunhos = newsletter.contar()
    return (
        _cabeca_secao(
            "Newsletter",
            "Posts",
            f"{publicados} publicados e {rascunhos} rascunhos. Um post nasce "
            "rascunho e só aparece em /novidades quando o publicas de propósito "
            "— dá para escrever a meio de uma aula sem ninguém ler por cima do "
            "ombro.",
        )
        + '<section class="pn-secao">'
        '<div class="pn-linha-titulo"><p class="olho">Todos os posts</p>'
        '<a class="pn-botao forte" href="/painel/newsletter?novo=1">'
        f'{icones.svg("mais", 14)}novo post</a></div>'
        f"{_lista_posts(participante)}</section>"
        + _biblioteca(participante)
    )


# ---------------------------------------------------------------- perfil


def _perfil(participante: str, contexto: dict) -> str:
    from app.interface import auth

    retrato = media.perfil_de(participante)
    imagem = (
        f'<img class="pn-retrato-grande" src="/perfil/{_e(retrato)}" alt="">'
        if retrato
        else f'<div class="pn-retrato-vazio">{icones.svg("pessoa", 34)}</div>'
    )
    simbolo = auth.simbolo_csrf(participante)
    apagar = (
        f'<form method="post" action="/painel/perfil">'
        f'<input type="hidden" name="csrf" value="{simbolo}">'
        f'<input type="hidden" name="accao" value="apagar">'
        f'<button class="pn-botao perigo" type="submit">'
        f'{icones.svg("lixo", 14)}remover foto</button></form>'
        if retrato
        else ""
    )
    return (
        _cabeca_secao(
            "Conta",
            "Perfil",
            "A foto aparece ao lado do teu nome nos posts da newsletter. "
            "Fica nesta máquina, em data/perfil, e não sai daqui.",
        )
        + '<section class="pn-secao"><div class="pn-perfil">'
        f"{imagem}"
        '<div class="lado-forma">'
        '<form method="post" action="/painel/perfil" enctype="multipart/form-data">'
        f'<input type="hidden" name="csrf" value="{simbolo}">'
        '<input type="hidden" name="accao" value="foto">'
        '<label class="pn-campo"><span>escolher imagem</span>'
        '<input type="file" name="foto" data-limites=\''
        + _e(json.dumps({e: media.LIMITE_PERFIL for e in media.EXTENSOES_PERFIL}))
        + '\' accept="'
        + ",".join(f".{e}" for e in media.EXTENSOES_PERFIL)
        + '" required></label>'
        f'<div class="pn-acoes"><button class="pn-botao forte" type="submit">'
        f'{icones.svg("guardar", 14)}guardar foto</button>{apagar}</div>'
        "</form>"
        f'<p class="pn-nota">Sessão iniciada como <strong>{_e(participante)}</strong>. '
        f"Formatos: {', '.join(sorted(media.EXTENSOES_PERFIL))}, até "
        f"{media.LIMITE_PERFIL // 1024 // 1024} MB. O ficheiro é verificado pelos "
        "primeiros bytes e não pela extensão — um <code>.png</code> que não seja "
        "um PNG é recusado.</p>"
        "</div></div></section>"
    )


# ------------------------------------------------------------------ JSON


def json_vivo(
    conexao, quero: str, desde: int = 0, origem: str = ""
) -> bytes:
    """Tudo o que o painel precisa de saber agora, num pedido so.

    Havia tres temporizadores - registo, presenca, operacoes - e tres pedidos
    por tique. O limitador de pedidos da casa deixa passar 120 por minuto e por
    participante: so a consola, de dois em dois segundos, gastava trinta, e na
    pagina de automatizacao eram sessenta antes de o administrador clicar em
    nada. Um pedido por tique poe isso em vinte e quatro e deixa o resto do
    orcamento para navegar.

    `quero` vem da propria pagina: a consola nao precisa de presencas, e a
    tabela de utilizadores nao precisa do estado das operacoes.
    """
    from app.interface import registo as registo_servidor

    pedidos = {parte.strip() for parte in quero.split(",") if parte.strip()}
    fora: dict = {}

    if "registo" in pedidos:
        linhas, ultimo = registo_servidor.desde(desde, 300)
        if origem:
            alvos = set(origem.split(","))
            linhas = [l for l in linhas if l["origem"] in alvos]
        fora["registo"] = {"linhas": linhas, "ultimo": ultimo}

    if "presenca" in pedidos:
        fora["presenca"] = _presencas_como_lista(conexao)

    if "operacoes" in pedidos:
        fora["operacoes"] = operacoes.todos()
        fora["ocupado"] = operacoes.ocupado()

    return json.dumps(fora, ensure_ascii=False).encode("utf-8")


def _presencas_como_lista(conexao) -> list[dict]:
    from app.interface import auth

    try:
        presentes = uso.presencas(conexao)
        ultimos = uso.ultimos_eventos(conexao)
    except Exception:
        presentes, ultimos = {}, {}
    agora = datetime.now(timezone.utc)
    fora = []
    for rotulo in sorted(set(auth.carregar_participantes().values())):
        marca = presentes.get(rotulo, {})
        idade = presenca.segundos_desde(marca.get("visto"), agora)
        fora.append(
            {
                "rotulo": rotulo,
                "online": presenca.esta_online(marca.get("visto"), agora),
                "visto": presenca.ha_quanto_tempo(idade),
                "aparelho": marca.get("dispositivo") or presenca.DESCONHECIDO,
                "faz": _a_fazer(ultimos.get(rotulo), marca.get("pagina")),
            }
        )
    return fora


def json_previa(corpo: str) -> bytes:
    return json.dumps(
        {"html": marcacao.para_html(corpo)}, ensure_ascii=False
    ).encode("utf-8")


# -------------------------------------------------------------- JavaScript

# Tres coisas que nao se fazem sem isto: a consola ao vivo, o estado de uma
# operacao enquanto corre, e a pre-visualizacao. O resto do painel funciona com
# o JavaScript desligado.
#
# `document.hidden` aparece em todos os temporizadores por uma razao aprendida:
# um separador escondido continua a disparar `setInterval`, e o painel deixado
# aberto num separador de fundo estaria a pedir ao servidor de dois em dois
# segundos durante horas, sem ninguem a ver.
# Cadeia CRUA, e isto nao e detalhe de estilo. Numa cadeia normal o Python
# interpreta as sequencias de escape antes de o JavaScript as ver: uma
# sequencia de mudanca de linha escrita para o JavaScript chegava ao browser
# como uma mudanca de linha a meio de um literal - erro de sintaxe - e a barra
# invertida duplicada de uma expressao regular chegava como uma so, a escapar
# o caractere seguinte. Com o prefixo cru, o que esta escrito e o que o
# browser recebe.
GUIAO = r"""
(function () {
  "use strict";

  var INTERVALO = 2500;

  function porId(id) { return document.getElementById(id); }

  // ---------------------------------------------- confirmar o irreversivel
  var formularios = document.querySelectorAll("form[data-confirmar]");
  for (var i = 0; i < formularios.length; i++) {
    formularios[i].addEventListener("submit", function (ev) {
      if (!window.confirm(this.getAttribute("data-confirmar"))) {
        ev.preventDefault();
      }
    });
  }

  // ------------------------------------------------------------- consola
  var consola = porId("consola");
  var desde = consola ? parseInt(consola.getAttribute("data-desde") || "0", 10) : 0;
  var origem = consola ? (consola.getAttribute("data-origem") || "") : "";
  var seguir = porId("seguir");
  var graves = porId("so-graves");
  var pulso = porId("pulso");

  function desenharLinha(l) {
    var div = document.createElement("div");
    div.className = "ln " + l.nivel;
    var partes = [["hora", l.momento.slice(11)], ["nivel", l.origem],
                  ["texto", l.texto]];
    for (var k = 0; k < partes.length; k++) {
      var s = document.createElement("span");
      s.className = partes[k][0];
      // textContent e nao innerHTML. Uma linha de registo leva consigo o que
      // alguem escreveu na caixa de busca: e a unica coisa nesta pagina que
      // nao foi escrita por mim.
      s.textContent = partes[k][1];
      div.appendChild(s);
    }
    return div;
  }

  function filtrar() {
    if (consola && graves) {
      consola.classList.toggle("so-graves", graves.checked);
    }
  }
  if (graves) { graves.addEventListener("change", filtrar); }
  filtrar();

  function aplicarRegisto(d) {
    if (!consola || !d) { return; }
    desde = d.ultimo;
    if (!d.linhas.length) { return; }
    var vazia = consola.querySelector(".ln .texto");
    if (vazia && vazia.textContent === "Nada registado ainda.") {
      consola.innerHTML = "";
    }
    for (var j = 0; j < d.linhas.length; j++) {
      consola.appendChild(desenharLinha(d.linhas[j]));
    }
    while (consola.children.length > 600) {
      consola.removeChild(consola.firstChild);
    }
    if (seguir && seguir.checked) { consola.scrollTop = consola.scrollHeight; }
  }

  // ------------------------------------------------------------ presenca
  function aplicarPresenca(lista) {
    if (!lista) { return; }
    for (var j = 0; j < lista.length; j++) {
      var pessoa = lista[j];
      var linha = document.querySelector(
        '[data-quem="' + pessoa.rotulo.replace(/["\\]/g, "") + '"]'
      );
      if (!linha) { continue; }
      var bolha = linha.querySelector(".pn-bolha");
      if (bolha) { bolha.classList.toggle("online", pessoa.online); }
      var palavra = linha.querySelector(".palavra");
      if (palavra) { palavra.textContent = pessoa.online ? "online" : "offline"; }
      var visto = linha.querySelector(".visto");
      if (visto) { visto.textContent = pessoa.visto; }
      var faz = linha.querySelector(".pn-faz");
      if (faz) { faz.textContent = pessoa.faz; }
    }
  }

  // ----------------------------------------------------------- operacoes
  var corriaAntes = false;
  function aplicarOperacoes(estados) {
    if (!estados) { return; }
    var algumaCorre = false;
    for (var nome in estados) {
      if (!Object.prototype.hasOwnProperty.call(estados, nome)) { continue; }
      var e = estados[nome];
      if (e.a_correr) { algumaCorre = true; }
      var cartao = document.querySelector('[data-operacao="' + nome + '"]');
      if (!cartao) { continue; }
      var resumo = cartao.querySelector(".resumo");
      if (resumo) { resumo.textContent = e.resumo || "\u2014"; }
    }
    // Quando a ultima operacao acaba, recarrega-se a pagina: o cartao final tem
    // selo, duracao e o botao outra vez ativo, e desenhar isso a mao em
    // JavaScript era manter o mesmo desenho em dois sitios.
    if (corriaAntes && !algumaCorre) { window.location.reload(); }
    corriaAntes = algumaCorre;
  }

  // -------------------------------------- um pedido por tique, nao tres
  //
  // Havia tres temporizadores. O limitador da casa deixa passar 120 pedidos por
  // minuto e por participante, e so a consola gastava trinta - na pagina de
  // automatizacao eram sessenta antes de se clicar em nada. Cada pagina diz o
  // que quer e vai buscar tudo de uma vez.
  var quero = [];
  if (consola) { quero.push("registo"); }
  if (document.querySelector("[data-vivo=presenca]")) { quero.push("presenca"); }
  if (document.querySelector("[data-vivo=operacoes]")) { quero.push("operacoes"); }

  function pulsar() {
    if (document.hidden || !quero.length) { return; }
    var url = "/painel/api/vivo?quero=" + quero.join(",") + "&desde=" + desde;
    if (origem) { url += "&origem=" + encodeURIComponent(origem); }
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        aplicarRegisto(d.registo);
        aplicarPresenca(d.presenca);
        aplicarOperacoes(d.operacoes);
        if (pulso) { pulso.classList.add("ligada"); }
      })
      .catch(function () {
        if (pulso) { pulso.classList.remove("ligada"); }
      });
  }

  if (quero.length) {
    if (consola) { consola.scrollTop = consola.scrollHeight; }
    setInterval(pulsar, INTERVALO);
    // Um separador escondido continua a disparar `setInterval` mas nao pinta
    // nada: o `document.hidden` acima corta o pedido, e este ouvinte faz a
    // primeira actualizacao no momento em que se volta ao separador.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { pulsar(); }
    });
  }

  // ------------------------------------ recusar o ficheiro grande antes de subir
  //
  // O servidor recusa pelo Content-Length, sem ler o corpo - defesa certa, mas
  // do lado de quem carrega parece uma falha de rede: a ligacao fecha-se a meio
  // do envio e nao ha resposta para mostrar. Aqui evita-se a subida inteira.
  var campos = document.querySelectorAll("input[type=file][data-limites]");
  for (var c = 0; c < campos.length; c++) {
    campos[c].addEventListener("change", function () {
      var limites;
      try { limites = JSON.parse(this.getAttribute("data-limites")); }
      catch (e) { return; }
      var ficheiro = this.files && this.files[0];
      if (!ficheiro) { return; }
      var pedacos = ficheiro.name.split(".");
      var extensao = pedacos.length > 1 ? pedacos.pop().toLowerCase() : "";
      var maximo = limites[extensao];
      if (!maximo) {
        window.alert("Formato nao aceito: ." + extensao +
                     "\nAceitos: " + Object.keys(limites).sort().join(", "));
        this.value = "";
        return;
      }
      if (ficheiro.size > maximo) {
        window.alert(
          "Este ficheiro tem " + (ficheiro.size / 1048576).toFixed(1) +
          " MB e o maximo para ." + extensao + " e " +
          Math.round(maximo / 1048576) + " MB."
        );
        this.value = "";
      }
    });
  }

  // ------------------------------------------------- editor da newsletter
  var caixa = porId("corpo-post");
  if (caixa) {
    var alvo = porId("previa");
    var espera = null;
    var pedido = null;

    function previa() {
      if (!alvo) { return; }
      if (espera) { clearTimeout(espera); }
      espera = setTimeout(function () {
        var corpo = new URLSearchParams();
        corpo.set("corpo", caixa.value);
        var forma = porId("forma-post");
        var simbolo = forma ? forma.querySelector("[name=csrf]") : null;
        if (simbolo) { corpo.set("csrf", simbolo.value); }
        if (pedido) { pedido.abort(); }
        pedido = new AbortController();
        fetch("/painel/api/previa", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: corpo.toString(),
          signal: pedido.signal
        })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            // innerHTML de proposito: este HTML veio do renderizador do
            // servidor, que escapa tudo antes de interpretar a marcacao. E
            // exactamente a mesma cadeia que o aluno vai receber - e e essa a
            // razao de a previa nao ser feita aqui.
            if (d) { alvo.innerHTML = d.html; }
          })
          .catch(function () {});
      }, 400);
    }

    function envolver(antes, depois) {
      var i = caixa.selectionStart, f = caixa.selectionEnd;
      var meio = caixa.value.slice(i, f);
      caixa.value = caixa.value.slice(0, i) + antes + meio + depois +
                    caixa.value.slice(f);
      caixa.focus();
      caixa.selectionStart = i + antes.length;
      caixa.selectionEnd = i + antes.length + meio.length;
      previa();
    }

    var ferramentas = document.querySelectorAll(".pn-ferramentas button");
    for (var t = 0; t < ferramentas.length; t++) {
      ferramentas[t].addEventListener("click", function () {
        envolver(this.getAttribute("data-antes") || "",
                 this.getAttribute("data-depois") || "");
      });
    }
    var inserir = document.querySelectorAll("[data-inserir]");
    for (var n = 0; n < inserir.length; n++) {
      inserir[n].addEventListener("click", function () {
        envolver("\n" + this.getAttribute("data-inserir") + "\n", "");
      });
    }
    caixa.addEventListener("input", previa);
  }
})();
"""
