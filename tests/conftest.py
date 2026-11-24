"""Dados sintéticos no formato do PYield, montados com o próprio motor (sem rede)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

import pandas as pd
import pytest

from dicurve.engine.calendario import CalendarioDU, vencimento_di1
from dicurve.engine.curva import pu_de_taxa
from dicurve.ingest import b3_di1

CAL = CalendarioDU.anbima()
DATA_BASE = dt.date(2026, 11, 23)
CODIGOS = ["DI1F27", "DI1N27", "DI1F28", "DI1F29", "DI1F30", "DI1F31", "DI1F33", "DI1F35"]


def registros_pyield(
    data_base: dt.date = DATA_BASE,
    codigos: list[str] = CODIGOS,
    taxa: Callable[[int], float] = lambda du: 0.137 + du * 7e-6,
) -> list[dict[str, Any]]:
    linhas = []
    for c in codigos:
        venc = vencimento_di1(c, CAL)
        du = CAL.contar(data_base, venc)
        tx = round(taxa(du), 5)
        linhas.append(
            {
                "data_referencia": data_base,
                "codigo_negociacao": c,
                "data_vencimento": venc,
                "dias_uteis": du,
                "taxa_ajuste": tx,
                "preco_ajuste": round(pu_de_taxa(tx, float(du)), 2),
                "taxa_forward": None,
                "dv01": None,
                "contratos_abertos": 1000,
                "coluna_ignorada": "x",
            }
        )
    return linhas


@pytest.fixture
def ajustes() -> pd.DataFrame:
    return b3_di1.normalizar(registros_pyield())


@pytest.fixture
def cal() -> CalendarioDU:
    return CAL
