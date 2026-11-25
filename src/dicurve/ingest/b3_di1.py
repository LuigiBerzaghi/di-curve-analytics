"""Ajustes diários do DI1 publicados pela B3, obtidos pelo PYield.

``baixar_ajustes`` é a única função que acessa a rede. ``normalizar`` converte os
registros do PYield para o formato do projeto e é testada sem rede.

Os dados brutos são de propriedade da B3: ficam em ``data/raw/`` (fora do Git).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.curva import CurvaPre

#: Coluna do PYield -> coluna do projeto.
COLUNAS: dict[str, str] = {
    "data_referencia": "data_base",
    "codigo_negociacao": "codigo",
    "data_vencimento": "vencimento",
    "dias_uteis": "du_b3",
    "taxa_ajuste": "taxa_ajuste",
    "preco_ajuste": "pu_ajuste",
    "taxa_forward": "forward_b3",
    "dv01": "dv01_b3",
    "contratos_abertos": "contratos_abertos",
}

ORDEM = list(COLUNAS.values())


def tem_pregao(cal: CalendarioDU, data: dt.date) -> bool:
    """Dia útil com pregão na B3. Em 24/12 e 31/12 a B3 não abre, mas o dia conta como DU."""
    return cal.eh_dia_util(data) and not (data.month == 12 and data.day in (24, 31))


def pregao_anterior(cal: CalendarioDU, data: dt.date) -> dt.date:
    """Último pregão estritamente antes de ``data``."""
    d = data - dt.timedelta(days=1)
    while not tem_pregao(cal, d):
        d -= dt.timedelta(days=1)
    return d


def normalizar(registros: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Registros do PYield -> tabela do projeto, ordenada por data-base e vencimento."""
    linhas = [{novo: r.get(antigo) for antigo, novo in COLUNAS.items()} for r in registros]
    df = pd.DataFrame(linhas, columns=ORDEM)
    if df.empty:
        return df
    for col in ("data_base", "vencimento"):
        df[col] = pd.to_datetime(df[col]).dt.date
    df["codigo"] = df["codigo"].astype(str).str.upper()
    df["du_b3"] = df["du_b3"].astype("Int64")
    df["contratos_abertos"] = df["contratos_abertos"].astype("Int64")
    for col in ("taxa_ajuste", "pu_ajuste", "forward_b3", "dv01_b3"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["data_base", "vencimento"], ignore_index=True)


def baixar_ajustes(datas: Sequence[dt.date]) -> pd.DataFrame:
    """Baixa os ajustes do DI1 nas datas pedidas (acessa a rede)."""
    import pyield as yd  # importado aqui: só esta função depende do PYield

    if not datas:
        return normalizar([])
    bruto = yd.di1.dados([d.strftime("%d-%m-%Y") for d in datas])
    return normalizar(bruto.to_dicts())


def curva_de_ajustes(df: pd.DataFrame) -> CurvaPre:
    """Curva DI de uma data-base a partir das taxas de ajuste (ignora linhas sem taxa)."""
    datas = df["data_base"].unique()
    if len(datas) != 1:
        raise ValueError(f"esperada uma única data-base, recebidas {len(datas)}")
    validos = df.dropna(subset=["taxa_ajuste", "du_b3"])
    validos = validos[validos["du_b3"] > 0]
    return CurvaPre(validos["du_b3"].astype(float), validos["taxa_ajuste"].astype(float))
