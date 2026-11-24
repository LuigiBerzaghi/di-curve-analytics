import numpy as np
import pytest

from dicurve.engine.cenarios import (
    CENARIOS_MACRO,
    REGIMES_INCLINACAO,
    ChoqueCurva,
    aplicar,
    delta_pv_total,
    inclinacao,
    paralelo,
)
from dicurve.engine.curva import CurvaDI
from dicurve.engine.risco import Posicao, delta_pv

CURVA = CurvaDI([252, 504, 756, 1260, 2520], [0.140, 0.135, 0.133, 0.132, 0.133])
CARTEIRA = [Posicao("a", 300, 100e6), Posicao("b", 900, -50e6), Posicao("c", 2000, 80e6)]


def test_paralelo_sobe_todos_os_vertices() -> None:
    nova = aplicar(CURVA, paralelo(100))
    np.testing.assert_allclose(nova.taxas - CURVA.taxas, 0.01, atol=1e-15)


def test_choque_zero_nao_muda_carteira() -> None:
    assert delta_pv_total(CARTEIRA, CURVA, paralelo(0)) == 0


def test_paralelo_igual_a_soma_das_posicoes() -> None:
    esperado = sum(delta_pv(p.pv, CURVA.taxa(float(p.du)), p.du, 100) for p in CARTEIRA)
    assert delta_pv_total(CARTEIRA, CURVA, paralelo(100)) == pytest.approx(esperado)


def test_inclinacao_interpola_entre_curto_e_longo() -> None:
    c = inclinacao(-50, 50, du_curto=0, du_longo=1000)
    assert c.em_prazo(500) == pytest.approx(0)
    assert c.em_prazo(-10) == pytest.approx(-50)  # constante fora dos extremos
    assert c.em_prazo(5000) == pytest.approx(50)


def test_regimes_tem_os_sinais_certos() -> None:
    bull_steep = REGIMES_INCLINACAO["Bull steepening"]
    assert bull_steep.em_prazo(63) < bull_steep.em_prazo(2520) < 0
    bear_flat = REGIMES_INCLINACAO["Bear flattening"]
    assert bear_flat.em_prazo(63) > bear_flat.em_prazo(2520) > 0


def test_cenarios_macro_tem_oito_prazos() -> None:
    for choque in CENARIOS_MACRO.values():
        assert len(choque.prazos_du) == len(choque.choques_bps) == 8


@pytest.mark.parametrize(
    ("prazos", "choques"), [((), ()), ((252.0, 100.0), (1.0, 2.0)), ((1.0,), (1.0, 2.0))]
)
def test_choque_invalido(prazos: tuple[float, ...], choques: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        ChoqueCurva(prazos, choques)
