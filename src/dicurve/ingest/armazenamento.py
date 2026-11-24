"""Armazenamento local dos dados brutos em Parquet, um arquivo por fonte e data.

A pasta padrão é ``data/raw/``, que está no ``.gitignore``: os dados da B3 nunca vão
para o repositório.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

RAIZ_PADRAO = Path("data/raw")


def caminho(fonte: str, data: dt.date, raiz: Path = RAIZ_PADRAO) -> Path:
    if not fonte.replace("_", "").isalnum():
        raise ValueError(f"nome de fonte inválido: {fonte!r}")
    return raiz / fonte / f"{data:%Y-%m-%d}.parquet"


def salvar(df: pd.DataFrame, fonte: str, data: dt.date, raiz: Path = RAIZ_PADRAO) -> Path:
    destino = caminho(fonte, data, raiz)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    df.to_parquet(temporario, index=False)
    temporario.replace(destino)  # escrita atômica: nunca deixa arquivo pela metade
    return destino


def ler(fonte: str, data: dt.date, raiz: Path = RAIZ_PADRAO) -> pd.DataFrame:
    df = pd.read_parquet(caminho(fonte, data, raiz))
    for col in ("data_base", "vencimento"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    return df


def datas_salvas(fonte: str, raiz: Path = RAIZ_PADRAO) -> list[dt.date]:
    pasta = raiz / fonte
    if not pasta.exists():
        return []
    return sorted(dt.date.fromisoformat(p.stem) for p in pasta.glob("*.parquet"))
