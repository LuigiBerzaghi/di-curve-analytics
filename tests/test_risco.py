import pytest
from hypothesis import given
from hypothesis import strategies as st

from dicurve.engine.curva import CurvaDI, pu_de_taxa
from dicurve.engine.risco import (
    Posicao,
    convexidade,
    delta_pv,
    delta_pv_aproximado,
    duration_modificada,
    dv01,
    key_rate_dv01,
    metricas_carteira,
)

CURVA = CurvaDI([252, 504, 756, 1260, 1764, 2520], [0.140, 0.135, 0.133, 0.132, 0.1325, 0.133])
CARTEIRA = [
    Posicao("F28", 283, 120e6),
    Posicao("F29", 533, -80e6),
    Posicao("F30", 784, 210e6),
    Posicao("F33", 1536, 75e6),
    Posicao("F37", 2546, -40e6),
]

taxas = st.floats(0.01, 0.30)
prazos = st.integers(1, 252 * 15)


def test_dmod_caso_a_mao() -> None:
    assert duration_modificada(0.10, 504) == pytest.approx(2 / 1.10)


def test_convexidade_caso_a_mao() -> None:
    assert convexidade(0.10, 252) == pytest.approx(2 / 1.10**2)


@given(taxas, prazos)
def test_dv01_analitico_igual_ao_numerico(taxa: float, du: int) -> None:
    pv = pu_de_taxa(taxa, float(du))
    numerico = pu_de_taxa(taxa - 0.5e-4, float(du)) - pu_de_taxa(taxa + 0.5e-4, float(du))
    assert dv01(pv, taxa, du) == pytest.approx(numerico, rel=1e-6)


@given(taxas, prazos)
def test_delta_pv_exato_bate_com_reprecificar(taxa: float, du: int) -> None:
    pv = pu_de_taxa(taxa, float(du))
    esperado = pu_de_taxa(taxa + 0.0100, float(du)) - pv
    assert delta_pv(pv, taxa, du, 100) == pytest.approx(esperado, rel=1e-10)


@given(taxas, prazos)
def test_choque_zero_nao_muda_nada(taxa: float, du: int) -> None:
    assert delta_pv(1e6, taxa, du, 0) == 0


@given(taxas, prazos)
def test_aproximacao_de_segunda_ordem_e_boa_para_choque_pequeno(taxa: float, du: int) -> None:
    exato = delta_pv(1e6, taxa, du, 5)
    assert delta_pv_aproximado(1e6, taxa, du, 5) == pytest.approx(exato, rel=1e-3, abs=1e-6)


def test_posicao_comprada_perde_com_alta() -> None:
    assert delta_pv(1e6, 0.13, 504, 100) < 0
    assert dv01(1e6, 0.13, 504) > 0


def test_convexidade_favorece_comprado() -> None:
    # alta e queda de mesmo tamanho: ganha mais na queda do que perde na alta
    assert delta_pv(1e6, 0.13, 2520, -200) > -delta_pv(1e6, 0.13, 2520, 200)


def test_soma_dos_key_rates_igual_ao_dv01_total() -> None:
    kr = key_rate_dv01(CARTEIRA, CURVA)
    assert sum(kr.values()) == pytest.approx(metricas_carteira(CARTEIRA, CURVA).dv01, rel=1e-12)


def test_key_rate_posicao_no_vertice_vai_toda_para_ele() -> None:
    kr = key_rate_dv01([Posicao("x", 504, 1e6)], CURVA)
    assert kr["2A"] == pytest.approx(sum(kr.values()))
    assert kr["1A"] == 0


def test_metricas_da_carteira() -> None:
    m = metricas_carteira(CARTEIRA, CURVA)
    assert m.pv_liquido == pytest.approx(285e6)
    assert m.pv_bruto == pytest.approx(525e6)
    assert m.dv01 == pytest.approx(sum(dv01(p.pv, CURVA.taxa(float(p.du)), p.du) for p in CARTEIRA))


def test_carteira_vazia() -> None:
    with pytest.raises(ValueError):
        metricas_carteira([], CURVA)
