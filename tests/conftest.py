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


# ---------- títulos públicos (dados abertos do BCB) ----------

VENC_LTN = [
    dt.date(2027, 4, 1),
    dt.date(2027, 10, 1),
    dt.date(2028, 7, 1),
    dt.date(2029, 7, 1),
    dt.date(2032, 1, 1),
]
VENC_NTNF = [dt.date(2029, 1, 1), dt.date(2035, 1, 1), dt.date(2037, 1, 1)]


def tabela_titulos(
    datas: list[dt.date], zero: Callable[[int], float] = lambda du: 0.14 + du * 6e-6
) -> pd.DataFrame:
    """Negociações sintéticas no formato de ``bcb_titulos``: LTN na curva zero e NTN-F
    precificadas pela mesma curva (consistentes por construção)."""
    from dicurve.engine.curva import CurvaPre
    from dicurve.engine.titulos import fluxos_ntnf, pu_ltn, pu_por_curva
    from dicurve.ingest.bcb_titulos import ORDEM

    linhas = []
    for i, d in enumerate(datas):
        prazos = list(range(1, 3200, 21))
        curva = CurvaPre(prazos, [zero(p) + i * 2e-4 for p in prazos])
        for v in VENC_LTN:
            du = CAL.contar(d, v)
            tx = round(float(curva.taxa(float(du))), 6)
            pu = pu_ltn(tx, du)
            linhas.append([d, "LTN", "100000", v, 10, 1000, pu, pu, pu, tx, tx, tx])
        for v in VENC_NTNF:
            pu = pu_por_curva(fluxos_ntnf(d, v, CAL), curva)
            linhas.append([d, "NTN-F", "950199", v, 10, 1000, pu, pu, pu, None, None, None])
    return pd.DataFrame(linhas, columns=ORDEM)
