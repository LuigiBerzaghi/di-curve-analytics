"""Séries do SGS (Banco Central): CDI anualizado e Selic meta.

Desde 26/03/2025 a API exige filtro de datas e limita cada consulta a 10 anos.
``baixar_serie`` divide períodos longos em janelas e junta o resultado.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

import pandas as pd

#: Nome -> código da série no SGS.
SERIES: dict[str, int] = {
    "cdi": 4389,  # CDI anualizado, base 252, % a.a.
    "selic_meta": 432,  # meta Selic definida pelo Copom, % a.a.
}

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
JANELA_MAX_ANOS = 10


class Resposta(Protocol):
    def raise_for_status(self) -> None: ...
    def json(self) -> Any: ...


Getter = Callable[..., Resposta]


def janelas(
    inicio: dt.date, fim: dt.date, anos: int = JANELA_MAX_ANOS
) -> list[tuple[dt.date, dt.date]]:
    """Divide ``[inicio, fim]`` em janelas contíguas de até ``anos`` anos."""
    if fim < inicio:
        raise ValueError("fim antes do início")
    saida: list[tuple[dt.date, dt.date]] = []
    atual = inicio
    while atual <= fim:
        try:
            limite = atual.replace(year=atual.year + anos) - dt.timedelta(days=1)
        except ValueError:  # 29/02 em ano não bissexto
            limite = atual.replace(year=atual.year + anos, day=28) - dt.timedelta(days=1)
        ate = min(limite, fim)
        saida.append((atual, ate))
        atual = ate + dt.timedelta(days=1)
    return saida


def parse_sgs(payload: Iterable[Mapping[str, Any]]) -> pd.Series:
    """Converte a resposta do SGS em série indexada por data, com taxa em fração (0,149)."""
    datas, valores = [], []
    for item in payload:
        datas.append(dt.datetime.strptime(str(item["data"]), "%d/%m/%Y").date())
        valores.append(float(str(item["valor"]).replace(",", ".")) / 100)
    serie = pd.Series(valores, index=pd.Index(datas, name="data"), dtype="float64")
    return serie[~serie.index.duplicated(keep="last")].sort_index()


def baixar_serie(
    codigo: int, inicio: dt.date, fim: dt.date, get: Getter | None = None, timeout: float = 30
) -> pd.Series:
    """Baixa uma série do SGS entre ``inicio`` e ``fim`` (acessa a rede)."""
    if get is None:
        import requests

        get = requests.get
    partes = []
    for a, b in janelas(inicio, fim):
        params = {
            "formato": "json",
            "dataInicial": a.strftime("%d/%m/%Y"),
            "dataFinal": b.strftime("%d/%m/%Y"),
        }
        resp = get(URL.format(codigo=codigo), params=params, timeout=timeout)
        resp.raise_for_status()
        partes.append(parse_sgs(resp.json()))
    if not partes:
        return pd.Series(dtype="float64")
    serie: pd.Series[float] = pd.concat(partes)
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    return serie
