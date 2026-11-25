import pytest
from hypothesis import given
from hypothesis import strategies as st

from dicurve.engine.curva import CurvaPre, fator_capitalizacao
from dicurve.engine.forwards import (
    forwards_entre_vertices,
    metricas_forma,
    spread_bps,
    taxa_forward,
)


def test_forward_caso_a_mao() -> None:
    # 1 ano a 10% e 2 anos a 12%: (1,12² / 1,10) − 1
    assert taxa_forward(252, 0.10, 504, 0.12) == pytest.approx(1.12**2 / 1.10 - 1, abs=1e-12)


def test_forward_exige_ordem() -> None:
    with pytest.raises(ValueError):
        taxa_forward(504, 0.1, 252, 0.1)


@given(st.integers(1, 3000), st.integers(21, 3000), st.floats(0.03, 0.3), st.floats(-300, 300))
def test_forward_reconstroi_a_taxa_longa(d1: int, extra: int, t1: float, spread: float) -> None:
    # Casos realistas: trechos de pelo menos 1 mês e taxas a até 300 bps uma da outra.
    # Fora disso a forward pode chegar perto de −100% (ex.: 25% → 12,5% em 1 DU), e
    # 1 + forward ≈ 1e-12 perde precisão em ponto flutuante, sem significado financeiro.
    d2, t2 = d1 + extra, t1 + spread * 1e-4
    f = taxa_forward(d1, t1, d2, t2)
    composto = fator_capitalizacao(t1, float(d1)) * fator_capitalizacao(f, float(extra))
    assert composto == pytest.approx(fator_capitalizacao(t2, float(d2)), rel=1e-10)


def test_forwards_entre_vertices_comecam_hoje() -> None:
    c = CurvaPre([252, 504], [0.10, 0.12])
    tr = forwards_entre_vertices(c)
    assert (tr[0].du_inicio, tr[0].du_fim, tr[0].taxa) == (0, 252, pytest.approx(0.10))
    assert tr[1].taxa == pytest.approx(1.12**2 / 1.10 - 1)


def test_curva_plana_tem_forwards_iguais_e_forma_zerada() -> None:
    c = CurvaPre([21, 252, 504, 756, 2520], [0.13] * 5)
    assert all(t.taxa == pytest.approx(0.13) for t in forwards_entre_vertices(c))
    m = metricas_forma(c)
    assert m.nivel == pytest.approx(0.13)
    assert m.inclinacao_bps == pytest.approx(0, abs=1e-9)
    assert m.curvatura_bps == pytest.approx(0, abs=1e-9)


def test_spread_em_bps() -> None:
    assert spread_bps(0.1350, 0.1326) == pytest.approx(-24.0)
