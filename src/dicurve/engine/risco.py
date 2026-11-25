"""Medidas de risco de taxa para posições prefixadas (zero cupom).

Sinais e unidades
-----------------
- ``pv`` em R$; positivo = posição comprada em PU (ganha quando a taxa cai).
- ``dv01`` = −ΔPV para uma alta de 1 bp, em R$. Positivo para posição comprada.
- Choques em bps somados à taxa a.a.
- A reprecificação de cenários é **exata**: ΔPV = PV · [(1+i)^t / (1+i+s)^t − 1].
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from dicurve import DIAS_UTEIS_ANO
from dicurve.engine.curva import CurvaPre

BP = 1e-4

#: Vértices de key rate, em dias úteis.
VERTICES_KEY_RATE: dict[str, int] = {
    "1A": 252,
    "2A": 504,
    "3A": 756,
    "5A": 1260,
    "7A": 1764,
    "10A": 2520,
}


def duration_macaulay(du: float) -> float:
    """Para um zero cupom, a duration de Macaulay é o próprio prazo em anos."""
    return du / DIAS_UTEIS_ANO


def duration_modificada(taxa: float, du: float) -> float:
    """Dmod = (du/252) / (1 + taxa): sensibilidade relativa do PV à taxa."""
    return duration_macaulay(du) / (1 + taxa)


def convexidade(taxa: float, du: float) -> float:
    """C = t(t+1) / (1+taxa)²: curvatura da relação PV × taxa."""
    t = duration_macaulay(du)
    return t * (t + 1) / (1 + taxa) ** 2


def dv01(pv: float, taxa: float, du: float) -> float:
    """DV01 analítico: PV · Dmod · 1 bp."""
    return pv * duration_modificada(taxa, du) * BP


def delta_pv(pv: float, taxa: float, du: float, choque_bps: float) -> float:
    """Variação exata do PV de um zero cupom quando a taxa sobe ``choque_bps``."""
    t = duration_macaulay(du)
    s = choque_bps * BP
    return float(pv * ((1 + taxa) ** t / (1 + taxa + s) ** t - 1))


def delta_pv_aproximado(pv: float, taxa: float, du: float, choque_bps: float) -> float:
    """Aproximação de 2ª ordem: −Dmod·PV·Δi + ½·C·PV·Δi². Só para comparação."""
    s = choque_bps * BP
    return pv * (-duration_modificada(taxa, du) * s + 0.5 * convexidade(taxa, du) * s**2)


@dataclass(frozen=True)
class Posicao:
    """Posição prefixada zero cupom: valor presente ``pv`` (R$) com vencimento em ``du``."""

    nome: str
    du: int
    pv: float


@dataclass(frozen=True)
class MetricasCarteira:
    pv_liquido: float
    pv_bruto: float
    dv01: float
    duration_modificada: float
    convexidade: float


def metricas_carteira(posicoes: Sequence[Posicao], curva: CurvaPre) -> MetricasCarteira:
    """PV, DV01 e médias de duration e convexidade ponderadas pelo PV líquido."""
    if not posicoes:
        raise ValueError("carteira vazia")
    taxas = [curva.taxa(float(p.du)) for p in posicoes]
    pv_liq = sum(p.pv for p in posicoes)
    dmod_pv = sum(p.pv * duration_modificada(r, p.du) for p, r in zip(posicoes, taxas, strict=True))
    conv_pv = sum(p.pv * convexidade(r, p.du) for p, r in zip(posicoes, taxas, strict=True))
    base = pv_liq if pv_liq != 0 else float("nan")
    return MetricasCarteira(
        pv_liquido=pv_liq,
        pv_bruto=sum(abs(p.pv) for p in posicoes),
        dv01=dmod_pv * BP,
        duration_modificada=dmod_pv / base,
        convexidade=conv_pv / base,
    )


def dv01_por_posicao(posicoes: Sequence[Posicao], curva: CurvaPre) -> dict[str, float]:
    return {p.nome: dv01(p.pv, curva.taxa(float(p.du)), p.du) for p in posicoes}


def key_rate_dv01(
    posicoes: Sequence[Posicao],
    curva: CurvaPre,
    vertices: dict[str, int] | None = None,
) -> dict[str, float]:
    """DV01 por vértice de key rate.

    O DV01 de cada posição é repartido entre os dois vértices vizinhos com peso linear
    no prazo (alocação triangular). Fora dos extremos, vai todo para o vértice da ponta.
    Assim a soma dos key rates é igual ao DV01 paralelo.
    """
    vertices = vertices or VERTICES_KEY_RATE
    nomes = list(vertices)
    prazos = np.array([vertices[n] for n in nomes], dtype=np.float64)
    resultado = dict.fromkeys(nomes, 0.0)
    for p in posicoes:
        valor = dv01(p.pv, curva.taxa(float(p.du)), p.du)
        pesos = _pesos_triangulares(float(p.du), prazos)
        for nome, w in zip(nomes, pesos, strict=True):
            resultado[nome] += valor * float(w)
    return resultado


def _pesos_triangulares(du: float, prazos: np.ndarray) -> np.ndarray:
    pesos = np.zeros_like(prazos)
    if du <= prazos[0]:
        pesos[0] = 1.0
    elif du >= prazos[-1]:
        pesos[-1] = 1.0
    else:
        j = int(np.searchsorted(prazos, du) - 1)
        w = (du - prazos[j]) / (prazos[j + 1] - prazos[j])
        pesos[j], pesos[j + 1] = 1 - w, w
    return pesos
