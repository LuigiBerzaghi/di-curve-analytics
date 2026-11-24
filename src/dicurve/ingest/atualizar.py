"""Coleta de um dia: baixa os ajustes do DI1, salva, verifica e imprime o relatório.

Uso:
    dicurve-atualizar                  # último pregão antes de hoje
    dicurve-atualizar --data 2026-11-23
    dicurve-atualizar --data 2026-11-23 --sem-bcb

Sai com código 1 se alguma verificação de gravidade "erro" falhar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path

from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import armazenamento, b3_di1, bcb
from dicurve.qa.verificacoes import aprovado, relatorio, verificar_di1


def ultimo_pregao(cal: CalendarioDU, hoje: dt.date) -> dt.date:
    """Último pregão antes de ``hoje``."""
    return b3_di1.pregao_anterior(cal, hoje)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Coleta e verifica os ajustes do DI1 de um dia.")
    p.add_argument("--data", type=dt.date.fromisoformat, help="data-base (AAAA-MM-DD)")
    p.add_argument(
        "--raiz", type=Path, default=armazenamento.RAIZ_PADRAO, help="pasta dos dados brutos"
    )
    p.add_argument("--sem-bcb", action="store_true", help="não baixa CDI e Selic")
    args = p.parse_args(argv)

    cal = CalendarioDU.anbima()
    data = args.data or ultimo_pregao(cal, dt.date.today())
    if not b3_di1.tem_pregao(cal, data):
        print(f"{data:%d/%m/%Y} não teve pregão na B3.", file=sys.stderr)
        return 2
    anterior = b3_di1.pregao_anterior(cal, data)

    df = b3_di1.baixar_ajustes([anterior, data])
    hoje_df = df[df["data_base"] == data]
    ant_df = df[df["data_base"] == anterior]
    if hoje_df.empty:
        print(f"Sem ajustes do DI1 para {data:%d/%m/%Y}.", file=sys.stderr)
        return 1
    armazenamento.salvar(hoje_df, "b3_di1", data, args.raiz)
    if not ant_df.empty:
        armazenamento.salvar(ant_df, "b3_di1", anterior, args.raiz)

    if not args.sem_bcb:
        for nome, codigo in bcb.SERIES.items():
            try:
                serie = bcb.baixar_serie(codigo, data - dt.timedelta(days=10), data)
                armazenamento.salvar(
                    serie.rename("valor").reset_index(), f"bcb_{nome}", data, args.raiz
                )
            except Exception as erro:  # BCB fora do ar não bloqueia a curva
                print(
                    f"Aviso: série {nome} do BCB indisponível ({type(erro).__name__}).",
                    file=sys.stderr,
                )

    resultados = verificar_di1(hoje_df, cal, ant_df)
    print(relatorio(resultados, f"DI1 {data:%d/%m/%Y} · {len(hoje_df)} contratos"))
    return 0 if aprovado(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
