"""A paginacao erra sempre nos limites, nunca no meio."""

from app.interface import paginacao


def test_conta_paginas_sem_uma_a_mais_no_multiplo_exato():
    """20 resultados de 10 em 10 sao 2 paginas, nao 3."""
    assert paginacao.calcular(20, 1).total_paginas == 2
    assert paginacao.calcular(21, 1).total_paginas == 3
    assert paginacao.calcular(19, 1).total_paginas == 2


def test_uma_pagina_quando_cabe_tudo():
    janela = paginacao.calcular(7, 1)
    assert janela.total_paginas == 1
    assert not janela.ha_seguinte
    assert not janela.ha_anterior


def test_lista_vazia_nao_rebenta():
    janela = paginacao.calcular(0, 1)
    assert (janela.pagina, janela.total_paginas, janela.inicio, janela.fim) == (1, 1, 0, 0)
    assert janela.fatiar([]) == []


def test_pagina_do_endereco_e_empurrada_para_dentro():
    """`pg=0`, `pg=-3` e `pg=9999` chegam do URL e nao podem dar erro."""
    assert paginacao.calcular(57, 0).pagina == 1
    assert paginacao.calcular(57, -3).pagina == 1
    assert paginacao.calcular(57, 9999).pagina == 6


def test_a_ultima_pagina_pode_vir_curta():
    janela = paginacao.calcular(57, 6)
    assert (janela.inicio, janela.fim) == (50, 57)
    assert len(janela.fatiar(list(range(57)))) == 7


def test_fatia_e_a_do_numero_da_pagina():
    itens = list(range(100))
    assert paginacao.calcular(100, 1).fatiar(itens)[0] == 0
    assert paginacao.calcular(100, 3).fatiar(itens) == list(range(20, 30))


def test_numeros_deslizam_em_vez_de_encolher():
    """Perto das pontas a barra tem de manter a largura, senao salta."""
    janela = paginacao.calcular(500, 1)
    assert paginacao.numeros(janela) == list(range(1, 11))
    janela = paginacao.calcular(500, 50)
    assert paginacao.numeros(janela) == list(range(41, 51))
    janela = paginacao.calcular(500, 25)
    assert len(paginacao.numeros(janela)) == 10
    assert 25 in paginacao.numeros(janela)


def test_numeros_nao_inventam_paginas_que_nao_existem():
    janela = paginacao.calcular(23, 1)
    assert paginacao.numeros(janela) == [1, 2, 3]


def test_pagina_um_nao_aparece_no_endereco():
    """Dois enderecos para a mesma pagina dividiriam o registo de uso."""
    assert paginacao.url({"q": "ficha"}, 1) == "/?q=ficha"
    assert paginacao.url({"q": "ficha"}, 2) == "/?q=ficha&pg=2"


def test_endereco_leva_filtros_e_deixa_cair_os_vazios():
    destino = paginacao.url({"q": "ficha", "d": "", "s": "material"}, 4)
    assert "d=" not in destino
    assert "s=material" in destino and "pg=4" in destino


def test_ler_aceita_so_numero_positivo():
    assert paginacao.ler("3") == 3
    assert paginacao.ler("") == 1
    assert paginacao.ler("0") == 1
    assert paginacao.ler("-2") == 1
    assert paginacao.ler("abc") == 1
    assert paginacao.ler("2; drop table") == 1
