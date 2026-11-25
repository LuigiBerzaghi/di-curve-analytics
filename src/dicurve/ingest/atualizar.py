"""Atualiza os dados abertos da curva pré e verifica o último dia.

Baixa os últimos meses de negociações de LTN e NTN-F (BCB) e o CDI (SGS 4389), junta com
o que já está em ``data/abertos/`` e roda as verificações do dia mais recente.

Uso:
    dicurve-atualizar                     # dia útil anterior a hoje
    dicurve-atualizar --data 2026-11-24

Códigos de saída: 0 aprovado; 1 reprovado ou dados atrasados; 3 o dia ainda não foi
publicado pelo BCB (normal de manhã cedo; o job tenta de novo mais tarde).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import bcb, bcb_titulos
from dicurve.qa.titulos import verificar_titulos
from dicurve.qa.verificacoes import aprovado, relatorio

RAIZ_PADRAO = Path("data/abertos")
ATRASO_MAXIMO_DU = 3


def caminho_titulos(raiz: Path) -> Path:
    return raiz / "titulos.csv"


def caminho_cdi(raiz: Path) -> Path:
    return raiz / "cdi.csv"


def ler_cdi(raiz: Path) -> pd.Series[float]:
    c = caminho_cdi(raiz)
    if not c.exists():
        return pd.Series(dtype="float64")
    df = pd.read_csv(c, sep=";")
    return pd.Series(df["cdi"].to_numpy(), index=pd.to_datetime(df["data"]).dt.date, name="cdi")


def gravar_cdi(serie: pd.Series[float], raiz: Path) -> None:
    c = caminho_cdi(raiz)
    c.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"data": [d.isoformat() for d in serie.index], "cdi": serie.to_numpy()}).to_csv(
        c, sep=";", index=False
    )


def meses_ate(data: dt.date, n: int) -> list[tuple[int, int]]:
    """Os ``n`` meses terminando no mês de ``data``, do mais antigo ao mais recente."""
    ano, mes = data.year, data.month
    out = []
    for _ in range(n):
        out.append((ano, mes))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return out[::-1]


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Atualiza LTN, NTN-F e CDI (BCB) e verifica o dia.")
    p.add_argument("--data", type=dt.date.fromisoformat, help="data-base (AAAA-MM-DD)")
    p.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="pasta dos dados abertos")
    p.add_argument("--meses", type=int, default=2, help="meses a baixar (padrão 2)")
    args = p.parse_args(argv)

    cal = CalendarioDU.anbima()
    data = args.data or cal.dia_util_anterior(dt.date.today() - dt.timedelta(days=1))

    arq = caminho_titulos(args.raiz)
    partes = [bcb_titulos.de_csv(arq)] if arq.exists() else []
    for ano, mes in meses_ate(data, args.meses):
        partes.append(bcb_titulos.baixar_mes(ano, mes))
    df = bcb_titulos.juntar(*partes)
    bcb_titulos.para_csv(df, arq)

    cdi = ler_cdi(args.raiz)
    try:
        novo = bcb.baixar_serie(bcb.SERIES["cdi"], data - dt.timedelta(days=45), data)
        cdi = pd.concat([cdi, novo])
        cdi = cdi[~cdi.index.duplicated(keep="last")].sort_index()
        gravar_cdi(cdi, args.raiz)
    except Exception as erro:  # CDI fora do ar: a curva sai sem a âncora curta
        print(f"Aviso: CDI indisponível ({type(erro).__name__}).", file=sys.stderr)

    datas = bcb_titulos.datas(df)
    if data not in datas:
        ultimo = datas[-1] if datas else None
        atraso = cal.contar(ultimo, data) if ultimo else ATRASO_MAXIMO_DU + 1
        print(
            f"{data:%d/%m/%Y} ainda não publicado pelo BCB; último dia: {ultimo}.", file=sys.stderr
        )
        return 1 if atraso > ATRASO_MAXIMO_DU else 3

    anteriores = [d for d in datas if d < data]
    taxa_cdi = float(cdi[data]) if data in cdi.index else None
    resultado = bcb_titulos.curva_do_dia(df, data, cal, taxa_cdi)
    curva_ant = None
    if anteriores:
        d0 = anteriores[-1]
        curva_ant = bcb_titulos.curva_do_dia(
            df, d0, cal, float(cdi[d0]) if d0 in cdi.index else None
        ).curva
    res = verificar_titulos(df, data, cal, resultado, curva_ant)
    print(relatorio(res, f"Curva pré {data:%d/%m/%Y} · LTN e NTN-F (BCB)"))
    return 0 if aprovado(res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
