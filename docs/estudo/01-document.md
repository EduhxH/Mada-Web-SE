# Estudo linha a linha — Sessão 1: app/models/document.py

## O arquivo

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Documento:
    id: int
    titulo: str
    texto: str
    origem: str
```

## O que cada linha faz

- `from dataclasses import dataclass` — traz UM nome (a função `dataclass`)
  do módulo da biblioteca padrão para o arquivo.
- `@dataclass(frozen=True)` — decorador: a classe entra crua e sai com
  métodos gerados automaticamente a partir da lista de campos:
  `__init__` (construtor), `__repr__` (representação legível),
  `__eq__` (igualdade POR VALOR, campo a campo).
  Com `frozen=True`, ganha também `__hash__` e um `__setattr__` que
  bloqueia qualquer atribuição depois da construção.
- `id: int` etc. — anotações de tipo: o `@dataclass` as lê para saber quais
  campos gerar; o Python NÃO as verifica em tempo de execução.

## Verdades verificadas no exercício

1. `doc.texto = "x"` levanta `FrozenInstanceError` no momento em que a linha
   roda (erro de execução, não de importação). Proteção: o documento
   atravessa fonte → índice → storage → resultado sem que ninguém possa
   corrompê-lo no caminho.
2. `Documento(1,"a","b","c") == Documento(1,"a","b","c")` é `True` (igualdade
   por valor, gerada pelo decorador). Sem o decorador seria `False`: o padrão
   de classes genéricas compara identidade (endereço de memória).
3. `Documento("sete", 1, 2, 3)` executa sem erro: anotações são documentação
   e insumo para ferramentas (mypy), não validação. Consequência: testes
   precisam verificar comportamento; o interpretador não barra tipo errado.
4. `frozen=True` viabiliza hash fixo → `Documento` pode viver em `set` e ser
   chave de `dict`. Se o objeto mudasse depois de inserido, o hash apontaria
   para a "gaveta" errada. Parente conceitual da Etapa 2: a tupla —
   "lista congelada", agora com campos nomeados.

## Detalhe extra (além do exercício)

Um dataclass NÃO congelado com `eq=True` (o padrão) fica **não-hasheável**:
o decorador define `__hash__ = None` de propósito, porque igualdade por valor
+ mutabilidade + hash é uma combinação que quebra sets/dicts silenciosamente.
Ou seja: `frozen=True` não só "permite" o hash — ele é o que o torna seguro.

## Custos

| Operação | Custo |
|---|---|
| Construir / ler campo | O(1) |
| Comparar com `==` | O(tamanho dos campos) — compara os textos |
| Hash | O(tamanho dos campos), calculado sob demanda |
