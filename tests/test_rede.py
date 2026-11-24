"""Testes com dados reais. Acessam a rede: rodam com ``pytest -m network``."""

import datetime as dt

import pytest

from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import b3_di1, bcb
from dicurve.qa.verificacoes import aprovado, relatorio, verificar_di1

pytestmark = pytest.mark.network


@pytest.mark.parametrize(
    "data",
    [
        dt.date(2026, 11, 23),
        dt.date(2025, 6, 2),
        dt.date(2023, 11, 1),  # antes de o 20/11 entrar na lista de feriados
    ],
)
def test_ajustes_reais_passam_nas_verificacoes(data: dt.date) -> None:
    df = b3_di1.baixar_ajustes([data])
    res = verificar_di1(df, CalendarioDU.anbima())
    assert aprovado(res), relatorio(res)
    assert all(r.ok for r in res if r.nome in {"dias_uteis", "pu_recalculado"})


def test_sem_regra_de_vigencia_o_du_de_2023_nao_bate() -> None:
    df = b3_di1.baixar_ajustes([dt.date(2023, 11, 1)])
    res = verificar_di1(df, CalendarioDU.anbima(considerar_vigencia=False))
    assert next(r for r in res if r.nome == "dias_uteis").ok is False


def test_series_do_bcb() -> None:
    for codigo in bcb.SERIES.values():
        s = bcb.baixar_serie(codigo, dt.date(2026, 11, 1), dt.date(2026, 11, 23))
        assert not s.empty
        assert 0.02 < s.iloc[-1] < 0.30
