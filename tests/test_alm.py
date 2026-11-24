import pytest

from dicurve.engine.alm import (
    FaixaBalanco,
    delta_eve,
    delta_nii,
    duration_gap,
    gaps,
    gaps_acumulados,
)
from dicurve.engine.cenarios import paralelo
from dicurve.engine.curva import CurvaDI

CURVA = CurvaDI([32, 151, 378, 882, 1890], [0.149, 0.146, 0.140, 0.134, 0.133])
BALANCO = [
    FaixaBalanco("≤ 3M", 32, 52.4e9, 58.2e9),
    FaixaBalanco("3–12M", 151, 38.1e9, 41.5e9),
    FaixaBalanco("1–2A", 378, 44.7e9, 30.9e9),
    FaixaBalanco("2–5A", 882, 61.3e9, 47.8e9),
    FaixaBalanco("> 5A", 1890, 27.6e9, 19.4e9),
]


def test_gaps() -> None:
    assert gaps(BALANCO)[0] == pytest.approx(-5.8e9)
    assert gaps_acumulados(BALANCO)[-1] == pytest.approx(sum(gaps(BALANCO)))


def test_balanco_casado_nao_tem_risco() -> None:
    casado = [FaixaBalanco("x", 500, 10e9, 10e9), FaixaBalanco("y", 1500, 5e9, 5e9)]
    assert delta_eve(casado, CURVA, paralelo(200)) == pytest.approx(0, abs=1e-3)
    assert delta_nii(casado, paralelo(200)) == 0
    assert duration_gap(casado, CURVA) == pytest.approx(0, abs=1e-12)


def test_ativo_mais_longo_perde_eve_com_alta() -> None:
    assert delta_eve(BALANCO, CURVA, paralelo(100)) < 0
    assert duration_gap(BALANCO, CURVA) > 0


def test_passivo_curto_maior_perde_margem_com_alta() -> None:
    # nas faixas até 12 meses há mais passivo que ativo
    assert delta_nii(BALANCO, paralelo(100)) < 0


def test_nii_caso_a_mao() -> None:
    faixa = [FaixaBalanco("x", 126, 10e9, 0)]
    # gap de 10 bi reprecifica no meio do ano: 10 bi × 1% × 0,5 ano
    assert delta_nii(faixa, paralelo(100)) == pytest.approx(10e9 * 0.01 * 0.5)


def test_faixa_alem_do_horizonte_nao_entra_no_nii() -> None:
    assert delta_nii([FaixaBalanco("x", 300, 10e9, 0)], paralelo(100)) == 0
