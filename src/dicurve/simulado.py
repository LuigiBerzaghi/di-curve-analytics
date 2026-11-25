"""Carteira e balanço **simulados** usados nas telas de risco e ALM.

Nada aqui vem de instituição financeira. As posições são definidas por prazo constante
(em dias úteis), e não por código de contrato, para que a carteira não "envelheça":
todo dia ela é reprecificada na curva do dia, sempre nos mesmos prazos.
"""

from __future__ import annotations

from dicurve.engine.alm import FaixaBalanco
from dicurve.engine.risco import Posicao

MI = 1e6
BI = 1e9

#: Prazo (DU) e PV (R$ mi) de cada posição. Positivo = dado (ganha se a taxa cai).
_CARTEIRA: tuple[tuple[str, int, float], ...] = (
    ("3M", 63, 120),
    ("1A", 252, -80),
    ("2A", 504, 210),
    ("3A", 756, 95),
    ("4A", 1008, -60),
    ("5A", 1260, 140),
    ("6A", 1512, 75),
    ("8A", 2016, 50),
    ("10A", 2520, -40),
    ("12A", 3024, 30),
)

#: Faixa, prazo médio (DU), ativos e passivos sensíveis (R$ bi).
_BALANCO: tuple[tuple[str, int, float, float], ...] = (
    ("≤ 3M", 32, 52.4, 58.2),
    ("3–12M", 151, 38.1, 41.5),
    ("1–2A", 378, 44.7, 30.9),
    ("2–5A", 882, 61.3, 47.8),
    ("> 5A", 1890, 27.6, 19.4),
)


def carteira() -> list[Posicao]:
    return [Posicao(nome, du, pv * MI) for nome, du, pv in _CARTEIRA]


def balanco() -> list[FaixaBalanco]:
    return [FaixaBalanco(nome, du, a * BI, p * BI) for nome, du, a, p in _BALANCO]
