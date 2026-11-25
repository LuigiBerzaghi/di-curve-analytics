"""Backfill: baixa e verifica os ajustes do DI1 dos últimos N pregões.

Uso:
    dicurve-b3-backfill                       # 250 pregões até o último dia útil
    dicurve-b3-backfill --pregoes 60 --ate 2026-11-23

Pula as datas já salvas. Cada dia passa pelas mesmas verificações da coleta diária,
usando o pregão anterior para a verificação de variação. Imprime uma linha por dia e
sai com código 1 se algum dia for reprovado.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import armazenamento, b3_di1
from dicurve.ingest.b3_atualizar import ultimo_pregao
from dicurve.qa.verificacoes import aprovado, verificar_di1


def pregoes(cal: CalendarioDU, ate: dt.date, n: int) -> list[dt.date]:
    """Os ``n`` pregões terminando em ``ate`` (inclusive), em ordem crescente."""
    if n < 1:
        raise ValueError("n deve ser ao menos 1")
    d = ate if b3_di1.tem_pregao(cal, ate) else b3_di1.pregao_anterior(cal, ate)
    datas = [d]
    while len(datas) < n:
        d = b3_di1.pregao_anterior(cal, d)
        datas.append(d)
    return datas[::-1]


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Baixa e verifica os últimos N pregões do DI1.")
    p.add_argument("--pregoes", type=int, default=250, help="quantos pregões (padrão 250)")
    p.add_argument("--ate", type=dt.date.fromisoformat, help="último pregão (AAAA-MM-DD)")
    p.add_argument("--lote", type=int, default=20, help="datas por requisição")
    p.add_argument(
        "--raiz", type=Path, default=armazenamento.RAIZ_PADRAO, help="pasta dos dados brutos"
    )
    args = p.parse_args(argv)

    cal = CalendarioDU.anbima()
    datas = pregoes(cal, args.ate or ultimo_pregao(cal, dt.date.today()), args.pregoes)
    salvas = set(armazenamento.datas_salvas("b3_di1", args.raiz))
    faltam = [d for d in datas if d not in salvas]
    for i in range(0, len(faltam), args.lote):
        lote = faltam[i : i + args.lote]
        df = b3_di1.baixar_ajustes(lote)
        for d in lote:
            dia = df[df["data_base"] == d]
            if not dia.empty:
                armazenamento.salvar(dia, "b3_di1", d, args.raiz)

    reprovados = sem_dado = 0
    anterior: pd.DataFrame | None = None
    for d in datas:
        try:
            dia = armazenamento.ler("b3_di1", d, args.raiz)
        except FileNotFoundError:
            print(f"{d:%d/%m/%Y}  sem dados")
            sem_dado += 1
            anterior = None
            continue
        res = verificar_di1(dia, cal, anterior)
        falhas = [r.nome for r in res if not r.ok]
        if not aprovado(res):
            reprovados += 1
        marca = "OK" if not falhas else ("REPROVADO" if not aprovado(res) else "ALERTA")
        print(f"{d:%d/%m/%Y}  {len(dia):>2} contratos  {marca:<9} {', '.join(falhas)}".rstrip())
        anterior = dia

    print(
        f"{len(datas)} pregões · {len(faltam)} baixados · "
        f"{reprovados} reprovados · {sem_dado} sem dados",
        file=sys.stderr,
    )
    return 1 if reprovados or sem_dado else 0


if __name__ == "__main__":
    raise SystemExit(main())
