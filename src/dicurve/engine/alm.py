"""ALM simplificado: gap de reprecificação, ΔEVE, ΔNII e duration gap.

O balanço é agregado em faixas de prazo; cada faixa é tratada como um fluxo zero cupom
no prazo médio. O balanço usado no projeto é **simulado**.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate

from dicurve import DIAS_UTEIS_ANO
from dicurve.engine.cenarios import ChoqueCurva
from dicurve.engine.curva import CurvaPre
from dicurve.engine.risco import BP, delta_pv, duration_modificada


@dataclass(frozen=True)
class FaixaBalanco:
    """Faixa de reprecificação: valores presentes de ativos e passivos em R$."""

    nome: str
    du_medio: int
    ativos: float
    passivos: float

    @property
    def gap(self) -> float:
        return self.ativos - self.passivos


def gaps(faixas: Sequence[FaixaBalanco]) -> list[float]:
    return [f.gap for f in faixas]


def gaps_acumulados(faixas: Sequence[FaixaBalanco]) -> list[float]:
    return list(accumulate(gaps(faixas)))


def delta_eve(faixas: Sequence[FaixaBalanco], curva: CurvaPre, choque: ChoqueCurva) -> float:
    """ΔEVE = ΣΔPV(ativos) − ΣΔPV(passivos), com reprecificação exata."""
    total = 0.0
    for f in faixas:
        taxa = curva.taxa(float(f.du_medio))
        s = choque.em_prazo(f.du_medio)
        total += delta_pv(f.ativos, taxa, f.du_medio, s) - delta_pv(f.passivos, taxa, f.du_medio, s)
    return total


def delta_nii(
    faixas: Sequence[FaixaBalanco], choque: ChoqueCurva, horizonte_du: int = DIAS_UTEIS_ANO
) -> float:
    """ΔNII no horizonte: Σ gap(faixa) × Δi × tempo restante no horizonte (em anos).

    Só entram as faixas que reprecificam dentro do horizonte; cada uma passa a render
    a nova taxa desde o seu prazo médio até o fim do horizonte. Balanço constante.
    """
    total = 0.0
    for f in faixas:
        if f.du_medio < horizonte_du:
            anos_restantes = (horizonte_du - f.du_medio) / DIAS_UTEIS_ANO
            total += f.gap * choque.em_prazo(f.du_medio) * BP * anos_restantes
    return total


def duration_gap(faixas: Sequence[FaixaBalanco], curva: CurvaPre) -> float:
    """D_ativo − D_passivo × (Passivo / Ativo), com durations modificadas ponderadas."""
    ativo = sum(f.ativos for f in faixas)
    passivo = sum(f.passivos for f in faixas)
    if ativo <= 0:
        raise ValueError("o total de ativos precisa ser positivo")

    def _dur(valores: list[tuple[float, int]], total: float) -> float:
        if total == 0:
            return 0.0
        return sum(v * duration_modificada(curva.taxa(float(du)), du) for v, du in valores) / total

    d_a = _dur([(f.ativos, f.du_medio) for f in faixas], ativo)
    d_p = _dur([(f.passivos, f.du_medio) for f in faixas], passivo)
    return d_a - d_p * passivo / ativo
