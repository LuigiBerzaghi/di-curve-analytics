"""Cenários de choque na curva e reprecificação exata da carteira.

Um choque é definido em alguns prazos (em bps) e interpolado linearmente entre eles,
constante fora dos extremos. Os cenários macro e de inclinação são **ilustrativos**.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from dicurve.engine.curva import CurvaDI, Vetor
from dicurve.engine.risco import Posicao, delta_pv


@dataclass(frozen=True)
class ChoqueCurva:
    """Choque em bps por prazo (dias úteis), interpolado linearmente."""

    prazos_du: tuple[float, ...]
    choques_bps: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.prazos_du) == 0 or len(self.prazos_du) != len(self.choques_bps):
            raise ValueError("prazos e choques precisam ter o mesmo tamanho, maior que zero")
        if any(b <= a for a, b in zip(self.prazos_du, self.prazos_du[1:], strict=False)):
            raise ValueError("prazos precisam ser estritamente crescentes")

    def em(self, du: ArrayLike) -> Vetor:
        """Choque em bps nos prazos pedidos."""
        x = np.asarray(du, dtype=np.float64)
        return np.interp(x, self.prazos_du, self.choques_bps)

    def em_prazo(self, du: float) -> float:
        return float(self.em(np.array([du]))[0])


def paralelo(bps: float) -> ChoqueCurva:
    return ChoqueCurva((1.0,), (float(bps),))


def inclinacao(
    curto_bps: float, longo_bps: float, du_curto: float = 63, du_longo: float = 2520
) -> ChoqueCurva:
    """Pivô linear entre ``du_curto`` (3M) e ``du_longo`` (10A)."""
    return ChoqueCurva((float(du_curto), float(du_longo)), (float(curto_bps), float(longo_bps)))


#: Prazos usados nos vetores de cenário: 3M, 6M, 1A, 2A, 3A, 5A, 7A, 10A.
PRAZOS_CENARIO = (63.0, 126.0, 252.0, 504.0, 756.0, 1260.0, 1764.0, 2520.0)

REGIMES_INCLINACAO: dict[str, ChoqueCurva] = {
    "Bull steepening": inclinacao(-60, -10),
    "Bear steepening": inclinacao(10, 70),
    "Bull flattening": inclinacao(-10, -60),
    "Bear flattening": inclinacao(70, 10),
}

CENARIOS_MACRO: dict[str, ChoqueCurva] = {
    "Copom hawkish": ChoqueCurva(PRAZOS_CENARIO, (75, 70, 60, 45, 35, 25, 20, 15)),
    "Estresse fiscal": ChoqueCurva(PRAZOS_CENARIO, (20, 30, 50, 90, 120, 150, 160, 170)),
    "Desinflação": ChoqueCurva(PRAZOS_CENARIO, (-50, -60, -70, -65, -55, -45, -40, -35)),
    "Risk-off global": ChoqueCurva(PRAZOS_CENARIO, (30, 40, 60, 80, 90, 95, 100, 100)),
}


def aplicar(curva: CurvaDI, choque: ChoqueCurva) -> CurvaDI:
    """Curva chocada: soma o choque às taxas dos vértices."""
    return curva.com_taxas(curva.taxas + choque.em(curva.du) * 1e-4)


def delta_pv_carteira(
    posicoes: Sequence[Posicao], curva: CurvaDI, choque: ChoqueCurva
) -> dict[str, float]:
    """ΔPV exato de cada posição, com o choque lido no prazo de cada uma."""
    return {
        p.nome: delta_pv(p.pv, curva.taxa(float(p.du)), p.du, choque.em_prazo(p.du))
        for p in posicoes
    }


def delta_pv_total(posicoes: Sequence[Posicao], curva: CurvaDI, choque: ChoqueCurva) -> float:
    return sum(delta_pv_carteira(posicoes, curva, choque).values())
