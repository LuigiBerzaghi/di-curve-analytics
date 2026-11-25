"""Filtra o CSV do Tesouro Direto: só títulos prefixados, a partir de uma data.

Mantém o formato original (separador ';', decimal ','). Uso no workflow:
    python scripts/extrair_prefixados.py entrada.csv saida.csv 2020-01-01
"""

import csv
import datetime as dt
import sys

PREFIXADOS = {"Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais"}


def main(entrada: str, saida: str, desde: str) -> None:
    corte = dt.date.fromisoformat(desde)
    bruto = open(entrada, "rb").read()
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    linhas = list(csv.reader(texto.splitlines(), delimiter=";"))
    cab, dados = linhas[0], linhas[1:]
    i_tipo, i_base = cab.index("Tipo Titulo"), cab.index("Data Base")
    tipos = sorted({r[i_tipo] for r in dados if r})
    print("tipos:", tipos)
    manter = [
        r for r in dados
        if r and r[i_tipo] in PREFIXADOS
        and dt.datetime.strptime(r[i_base], "%d/%m/%Y").date() >= corte
    ]
    manter.sort(key=lambda r: (dt.datetime.strptime(r[i_base], "%d/%m/%Y"), r[i_tipo], r[1]))
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(cab)
        w.writerows(manter)
    print(f"{len(manter)} linhas de {len(dados)}; última data-base: {manter[-1][i_base]}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
