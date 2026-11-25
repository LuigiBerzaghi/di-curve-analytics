"""Taxas a termo, spreads e métricas de forma da curva."""

from __future__ import annotations

from dataclasses import dataclass

from dicurve import DIAS_UTEIS_ANO
from dicurve.engine.curva import VERTICES_PADRAO, CurvaPre


def taxa_forward(du1: float, taxa1: float, du2: float, taxa2: float) -> float:
    """Taxa a termo entre dois prazos: [(1+i₂)^t₂ / (1+i₁)^t₁]^(1/(t₂−t₁)) − 1, com t = du/252.

    É a taxa que deixa indiferente aplicar direto até ``du2`` ou aplicar até ``du1`` e renovar.
    """
    if du2 <= du1:
        raise ValueError("du2 precisa ser maior que du1")
    t1, t2 = du1 / DIAS_UTEIS_ANO, du2 / DIAS_UTEIS_ANO
    return float(((1 + taxa2) ** t2 / (1 + taxa1) ** t1) ** (1 / (t2 - t1)) - 1)


@dataclass(frozen=True)
class TrechoForward:
    du_inicio: int
    du_fim: int
    taxa: float


def forwards_entre_vertices(curva: CurvaPre) -> list[TrechoForward]:
    """Forward de cada trecho entre vértices consecutivos. O primeiro trecho começa em hoje."""
    trechos: list[TrechoForward] = []
    du_ant, tx_ant = 0.0, 0.0
    for du, tx in zip(curva.du, curva.taxas, strict=True):
        fwd = float(tx) if du_ant == 0 else taxa_forward(du_ant, tx_ant, float(du), float(tx))
        trechos.append(TrechoForward(int(du_ant), int(du), fwd))
        du_ant, tx_ant = float(du), float(tx)
    return trechos


def spread_bps(taxa_curta: float, taxa_longa: float) -> float:
    """Spread em bps: (taxa longa − taxa curta) × 10.000."""
    return (taxa_longa - taxa_curta) * 1e4


@dataclass(frozen=True)
class MetricasForma:
    """Nível (taxa de 2A), inclinação (10A − 2A) e curvatura (1A − 2·2A + 3A)."""

    nivel: float
    inclinacao_bps: float
    curvatura_bps: float


def metricas_forma(curva: CurvaPre) -> MetricasForma:
    v = curva.vertices_padrao()
    return MetricasForma(
        nivel=v["2A"],
        inclinacao_bps=spread_bps(v["2A"], v["10A"]),
        curvatura_bps=(v["1A"] - 2 * v["2A"] + v["3A"]) * 1e4,
    )


__all__ = [
    "VERTICES_PADRAO",
    "MetricasForma",
    "TrechoForward",
    "forwards_entre_vertices",
    "metricas_forma",
    "spread_bps",
    "taxa_forward",
]
