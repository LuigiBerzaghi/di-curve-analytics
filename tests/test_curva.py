import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from dicurve.engine.curva import (
    CurvaDI,
    fator_desconto,
    pu_de_taxa,
    taxa_de_pu,
)

taxas = st.floats(min_value=0.005, max_value=0.40)
prazos = st.integers(min_value=1, max_value=252 * 30)

CURVA = CurvaDI(
    [32, 283, 533, 784, 1034, 1285, 1536, 2041, 2546, 3302],
    [0.1446, 0.1412, 0.1374, 0.1349, 0.1334, 0.1327, 0.1326, 0.1329, 0.1333, 0.1338],
)


# Casos conferidos à mão
def test_pu_em_um_ano() -> None:
    assert pu_de_taxa(0.135, 252) == pytest.approx(100_000 / 1.135, abs=1e-9)


def test_pu_em_dois_anos() -> None:
    assert pu_de_taxa(0.135, 504) == pytest.approx(100_000 / 1.135**2, abs=1e-9)


def test_pu_de_meio_ano_usa_capitalizacao_exponencial() -> None:
    assert pu_de_taxa(0.10, 126) == pytest.approx(100_000 / 1.10**0.5, abs=1e-9)


def test_taxa_de_pu_exige_prazo_positivo() -> None:
    with pytest.raises(ValueError, match="positivo"):
        taxa_de_pu(90_000.0, 0.0)


@given(taxas, prazos)
def test_pu_taxa_pu_volta_ao_mesmo_valor(taxa: float, du: int) -> None:
    pu = pu_de_taxa(taxa, float(du))
    assert pu_de_taxa(taxa_de_pu(pu, float(du)), float(du)) == pytest.approx(pu, rel=1e-12)


@given(taxas, prazos)
def test_fator_de_desconto_entre_zero_e_um(taxa: float, du: int) -> None:
    assert 0 < fator_desconto(taxa, float(du)) < 1


def test_curva_passa_exatamente_pelos_vertices() -> None:
    np.testing.assert_allclose(CURVA.taxa(CURVA.du), CURVA.taxas, rtol=0, atol=1e-14)


def test_forward_constante_dentro_do_trecho() -> None:
    a, b = 533.0, 784.0
    f_total = CURVA.forward(a, b)
    for x in (560.0, 600.0, 700.0, 780.0):
        assert CURVA.forward(a, x) == pytest.approx(f_total, abs=1e-12)
        assert CURVA.forward(x, b) == pytest.approx(f_total, abs=1e-12)


def test_pontas_usam_taxa_do_vertice_mais_proximo() -> None:
    assert CURVA.taxa(10.0) == pytest.approx(CURVA.taxas[0], abs=1e-14)
    assert CURVA.taxa(0.0) == pytest.approx(CURVA.taxas[0], abs=1e-14)
    assert CURVA.taxa(5000.0) == pytest.approx(CURVA.taxas[-1], abs=1e-14)


def test_pu_da_curva_bate_com_formula() -> None:
    du = 1034.0
    assert CURVA.pu(du) == pytest.approx(pu_de_taxa(CURVA.taxa(du), du), rel=1e-12)


def test_escalar_entra_escalar_sai() -> None:
    assert isinstance(CURVA.taxa(400.0), float)
    assert isinstance(CURVA.taxa(np.array([400.0, 500.0])), np.ndarray)


def test_vertices_padrao() -> None:
    v = CURVA.vertices_padrao()
    assert list(v) == ["1M", "3M", "6M", "1A", "2A", "3A", "5A", "7A", "10A"]
    assert v["1M"] == pytest.approx(CURVA.taxas[0])


def test_vertices_fora_de_ordem_sao_ordenados() -> None:
    c = CurvaDI([504, 252], [0.13, 0.14])
    np.testing.assert_array_equal(c.du, [252, 504])
    np.testing.assert_array_equal(c.taxas, [0.14, 0.13])


@pytest.mark.parametrize(
    ("du", "tx"),
    [
        ([], []),
        ([252, 252], [0.1, 0.11]),
        ([0, 252], [0.1, 0.1]),
        ([252], [-1.5]),
        ([252], [0.1, 0.2]),
    ],
)
def test_curva_invalida(du: list[int], tx: list[float]) -> None:
    with pytest.raises(ValueError):
        CurvaDI(du, tx)


@given(st.lists(st.tuples(st.integers(1, 800), taxas), min_size=2, max_size=12))
def test_forwards_positivas_implicam_fator_de_desconto_decrescente(
    trechos: list[tuple[int, float]],
) -> None:
    # Monta a curva a partir de forwards positivas. Só taxas positivas não bastam:
    # 37,5% em 84 DU e 25% em 104 DU dão forward negativa entre os dois prazos.
    du = np.cumsum([d for d, _ in trechos]).astype(float)
    log_fator = np.cumsum([d / 252 * np.log1p(f) for d, f in trechos])
    tx = np.expm1(log_fator * 252 / du)
    c = CurvaDI(du, tx)
    grade = np.linspace(1, float(du[-1]) * 1.2, 400)
    assert np.all(np.diff(c.fator_desconto(grade)) < 0)


def test_taxas_positivas_podem_ter_forward_negativa() -> None:
    c = CurvaDI([84, 104], [0.375, 0.25])
    assert c.forward(84, 104) < 0
