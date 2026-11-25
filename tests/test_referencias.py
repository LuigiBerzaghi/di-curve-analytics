"""Comparações com referências externas: calendário ANBIMA do bizdays e funções do PYield.

Não acessam a rede: as duas bibliotecas trazem os feriados e as fórmulas embutidos.
"""

import datetime as dt

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dicurve.engine.calendario import CalendarioDU, feriados_nacionais
from dicurve.engine.curva import CurvaPre
from dicurve.engine.forwards import taxa_forward

bizdays = pytest.importorskip("bizdays")
yd = pytest.importorskip("pyield")

CAL = CalendarioDU.anbima()
CAL_SEM_VIGENCIA = CalendarioDU.anbima(considerar_vigencia=False)
ANBIMA = bizdays.Calendar.load(name="ANBIMA")
datas = st.dates(min_value=dt.date(2001, 1, 1), max_value=dt.date(2078, 12, 31))


@pytest.mark.parametrize("ano", range(2001, 2079))
def test_feriados_iguais_ao_calendario_anbima(ano: int) -> None:
    referencia = {d for d in ANBIMA.holidays if d.year == ano}
    assert set(feriados_nacionais(ano)) == referencia


@settings(max_examples=300)
@given(datas, datas)
def test_contagem_igual_ao_bizdays(a: dt.date, b: dt.date) -> None:
    # O bizdays usa sempre a lista atual de feriados e ajusta datas finais que não são
    # dias úteis. No uso real data-base e vencimento são dias úteis, então a comparação
    # é feita entre dias úteis.
    inicio = CAL_SEM_VIGENCIA.dia_util_seguinte(min(a, b))
    fim = CAL_SEM_VIGENCIA.dia_util_seguinte(max(a, b))
    assert CAL_SEM_VIGENCIA.contar(inicio, fim) == int(ANBIMA.bizdays(inicio, fim))


@settings(max_examples=100)
@given(datas, datas)
def test_contagem_igual_ao_pyield(a: dt.date, b: dt.date) -> None:
    inicio, fim = min(a, b), max(a, b)
    assert CAL.contar(inicio, fim) == int(yd.du.contar(inicio, fim))


VERT_DU = [32, 283, 533, 784, 1034, 1285, 1536, 2041, 2546, 3302]
VERT_TX = [0.1446, 0.1412, 0.1374, 0.1349, 0.1334, 0.1327, 0.1326, 0.1329, 0.1333, 0.1338]


def test_flat_forward_igual_ao_interpolador_do_pyield() -> None:
    nossa = CurvaPre(VERT_DU, VERT_TX)
    ref = yd.Interpolador(VERT_DU, VERT_TX, metodo="flat_forward", extrapolar=True)
    for du in [1, 10, 32, 100, 283, 400, 777, 1500, 2600, 3302, 4000]:
        assert nossa.taxa(float(du)) == pytest.approx(float(ref(du)), abs=1e-12), du


@given(st.integers(1, 3000), st.integers(1, 3000), st.floats(0.01, 0.3), st.floats(0.01, 0.3))
def test_forward_igual_ao_pyield(d1: int, extra: int, t1: float, t2: float) -> None:
    d2 = d1 + extra
    assert taxa_forward(d1, t1, d2, t2) == pytest.approx(yd.forward(d1, d2, t1, t2), rel=1e-10)


def test_curva_vetorizada_igual_ao_pyield() -> None:
    nossa = CurvaPre(VERT_DU, VERT_TX)
    ref = yd.Interpolador(VERT_DU, VERT_TX, metodo="flat_forward", extrapolar=True)
    grade = np.arange(1, 3500, 7)
    esperado = np.array([float(ref(int(d))) for d in grade])
    np.testing.assert_allclose(nossa.taxa(grade.astype(float)), esperado, atol=1e-12)
