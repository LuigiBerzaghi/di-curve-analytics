"""Negociações de LTN e NTN-F no mercado secundário (BCB, Selic, licença ODbL).

Fonte: "Negociação de Títulos Federais no Mercado Secundário", operações definitivas
extragrupo registradas no Selic, um ZIP por mês. A taxa média só vem para LTN; para a
NTN-F o motor calcula a taxa a partir do PU médio.

``baixar_mes`` é a única função que acessa a rede. O resto é puro e testado sem rede.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.titulos import Ltn, Ntnf, ResultadoBootstrap, bootstrap, fluxos_ntnf, taxa_ltn

URL = "https://www4.bcb.gov.br/pom/demab/negociacoes/download/NegE{aaaamm}.ZIP"
#: Código Selic → sigla. 950198 são os principais separados (strips) da NTN-F: ficam fora.
CODIGOS = {"100000": "LTN", "950199": "NTN-F"}
FONTE = "BCB, negociações de títulos federais no Selic (ODbL); cálculo próprio"

COLUNAS = {
    "DATA MOV": "data_base",
    "SIGLA": "sigla",
    "CODIGO": "codigo",
    "VENCIMENTO": "vencimento",
    "NUM DE OPER": "num_oper",
    "QUANT NEGOCIADA": "quantidade",
    "PU MIN": "pu_min",
    "PU MED": "pu_med",
    "PU MAX": "pu_max",
    "TAXA MIN": "taxa_min",
    "TAXA MED": "taxa_med",
    "TAXA MAX": "taxa_max",
}
ORDEM = list(COLUNAS.values())


def _texto(bruto: bytes) -> str:
    try:
        return bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        return bruto.decode("latin-1")


def ler_csv(texto: str) -> pd.DataFrame:
    """CSV do BCB (formato original) → tabela do projeto, só LTN e NTN-F com PU médio.

    Taxas viram fração (13,90 → 0,1390). Ordenada por data-base, sigla e vencimento.
    """
    linhas = texto.splitlines()
    inicio = next((k for k, ln in enumerate(linhas) if ln.upper().startswith("DATA MOV")), None)
    if inicio is None:
        return pd.DataFrame(columns=ORDEM)
    bruto = pd.read_csv(io.StringIO("\n".join(linhas[inicio:])), sep=";", dtype=str)
    bruto.columns = [c.strip().upper() for c in bruto.columns]
    df = bruto[list(COLUNAS)].rename(columns=COLUNAS)
    df["codigo"] = df["codigo"].str.strip()
    df = df[df["codigo"].isin(CODIGOS)].copy()
    df["sigla"] = df["codigo"].map(CODIGOS)
    for col in ("data_base", "vencimento"):
        df[col] = pd.to_datetime(df[col], format="%d/%m/%Y").dt.date
    for col in ORDEM[4:]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")
    for col in ("taxa_min", "taxa_med", "taxa_max"):
        df[col] = df[col] / 100
    df = df.dropna(subset=["pu_med"])
    return df[ORDEM].sort_values(["data_base", "sigla", "vencimento"], ignore_index=True)


def ler_zip(bruto: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(bruto)) as z:
        partes = [ler_csv(_texto(z.read(nome))) for nome in z.namelist()]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=ORDEM)


def ler_arquivo(caminho: Path) -> pd.DataFrame:
    return ler_csv(_texto(caminho.read_bytes()))


def juntar(*tabelas: pd.DataFrame) -> pd.DataFrame:
    """Junta recortes; em caso de repetição (data, sigla, vencimento) fica o mais recente."""
    df = pd.concat(tabelas, ignore_index=True)
    df = df.drop_duplicates(["data_base", "sigla", "vencimento"], keep="last")
    return df.sort_values(["data_base", "sigla", "vencimento"], ignore_index=True)


def baixar_mes(
    ano: int, mes: int, get: Callable[..., Any] | None = None, timeout: float = 60
) -> pd.DataFrame:
    """Baixa o ZIP de um mês (acessa a rede)."""
    if get is None:
        import requests  # importado aqui: só esta função depende de requests

        get = requests.get
    resp = get(URL.format(aaaamm=f"{ano}{mes:02d}"), timeout=timeout)
    resp.raise_for_status()
    return ler_zip(resp.content)


def ler_cdi(caminho: Path) -> pd.Series[float]:
    """Série 4389 do SGS salva em JSON → série diária em fração."""
    from dicurve.ingest.bcb import parse_sgs

    return parse_sgs(json.loads(caminho.read_text(encoding="utf-8")))


def titulos_do_dia(
    df: pd.DataFrame, data: dt.date, cal: CalendarioDU
) -> tuple[list[Ltn], list[Ntnf]]:
    """LTN e NTN-F negociadas na data, prontas para o bootstrapping."""
    dia = df[df["data_base"] == data]
    ltns = []
    for venc, taxa, pu in zip(
        *(dia[dia["sigla"] == "LTN"][c] for c in ("vencimento", "taxa_med", "pu_med")), strict=True
    ):
        du = cal.contar(data, venc)
        if du > 0:
            tx = float(taxa) if pd.notna(taxa) else taxa_ltn(float(pu), du)
            ltns.append(Ltn(venc, du, tx))
    ntnfs = []
    for venc, pu in zip(
        *(dia[dia["sigla"] == "NTN-F"][c] for c in ("vencimento", "pu_med")), strict=True
    ):
        fluxos = fluxos_ntnf(data, venc, cal)
        if fluxos:
            ntnfs.append(Ntnf(venc, tuple(fluxos), float(pu)))
    return ltns, ntnfs


def curva_do_dia(
    df: pd.DataFrame, data: dt.date, cal: CalendarioDU, cdi: float | None = None
) -> ResultadoBootstrap:
    """Curva pré do dia; com ``cdi``, a ponta curta é ancorada no CDI (1 DU)."""
    ltns, ntnfs = titulos_do_dia(df, data, cal)
    return bootstrap(ltns, ntnfs, ancora_cdi=cdi)


def datas(df: pd.DataFrame) -> list[dt.date]:
    return sorted(set(df["data_base"]))


def para_csv(df: pd.DataFrame, destino: Path) -> None:
    """Grava a tabela normalizada (separador ';', decimal '.', taxas em fração)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, sep=";", index=False)


def de_csv(origem: Path) -> pd.DataFrame:
    df = pd.read_csv(origem, sep=";", dtype={"codigo": str})
    for col in ("data_base", "vencimento"):
        df[col] = pd.to_datetime(df[col]).dt.date
    return df[ORDEM]
