"""Defesas para quando o servidor deixa de estar so na rede local.

Assim que existe um URL publico, bots encontram-no - nao por malicia, varrem
tudo. E um codigo de acesso exposto convida a tentativa de forca bruta.
"""

import re
import threading
import time
from collections import defaultdict, deque

# Limite geral: uma pessoa a pesquisar depressa faz ~20 pedidos/min
# (pagina + preview + sugestoes). 120 e folgado sem deixar passar um bot.
PEDIDOS_POR_MINUTO = 120
JANELA_GERAL = 60

# Entrada: 5 tentativas por 15 minutos. Com codigos de 8 caracteres num
# alfabeto de 32, forca bruta levaria mais tempo que o universo.
TENTATIVAS_ENTRADA = 5
JANELA_ENTRADA = 900

# Cabecalhos que fecham classes inteiras de ataque, a custo zero.
CABECALHOS_SEGURANCA = {
    # nao adivinhar o tipo de conteudo (evita HTML servido como imagem)
    "X-Content-Type-Options": "nosniff",
    # ninguem pode por o site dentro de um iframe (clickjacking)
    "X-Frame-Options": "DENY",
    # nao revelar o URL de origem a outros sites
    "Referrer-Policy": "no-referrer",
    # so recursos proprios; sem eval; sem plugins
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

_PADRAO_NOME_SEGURO = re.compile(r'[^A-Za-z0-9 ._()\[\]-]')


def sanear_nome_ficheiro(nome: str) -> str:
    """Neutraliza injecao de cabecalho pelo nome do ficheiro.

    Um ficheiro dentro de um ZIP chamado  evil".pdf\\r\\nX-Coisa: sim
    entraria no cabecalho Content-Disposition e acrescentaria cabecalhos
    escolhidos por quem preparou o ZIP.
    """
    limpo = _PADRAO_NOME_SEGURO.sub("_", nome).strip()
    # Se so sobraram separadores, o nome nao diz nada a ninguem
    if not any(c.isalnum() for c in limpo):
        return "documento"
    return limpo[:120]


class Limitador:
    """Janela deslizante por endereco, em memoria.

    Nao substitui a protecao volumetrica do tunel (essa absorve o trafego
    antes de chegar aqui); protege do abuso ao nivel da aplicacao.
    """

    def __init__(self, maximo: int, janela: int):
        self.maximo = maximo
        self.janela = janela
        self._registos: dict[str, deque] = defaultdict(deque)
        self._tranca = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = time.monotonic()
        with self._tranca:
            marcas = self._registos[chave]
            while marcas and agora - marcas[0] > self.janela:
                marcas.popleft()
            if len(marcas) >= self.maximo:
                return False
            marcas.append(agora)
            return True

    def restantes(self, chave: str) -> int:
        with self._tranca:
            return max(0, self.maximo - len(self._registos[chave]))

    def limpar(self, chave: str) -> None:
        with self._tranca:
            self._registos.pop(chave, None)

    def esquecer_antigos(self) -> None:
        agora = time.monotonic()
        with self._tranca:
            vazios = [
                chave
                for chave, marcas in self._registos.items()
                if not marcas or agora - marcas[-1] > self.janela
            ]
            for chave in vazios:
                del self._registos[chave]


def endereco_do_pedido(manipulador) -> str:
    """Endereco real de quem pede.

    Atras de um tunel, a ligacao vem sempre de 127.0.0.1 e o endereco
    verdadeiro chega em CF-Connecting-IP. So confiamos nesse cabecalho quando
    a ligacao e mesmo local - caso contrario qualquer um o forjava.
    """
    ligacao = manipulador.client_address[0]
    if ligacao in ("127.0.0.1", "::1"):
        real = manipulador.headers.get("CF-Connecting-IP")
        if real:
            return real.strip()[:45]
    return ligacao
