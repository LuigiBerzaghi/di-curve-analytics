"""Junta os ZIPs mensais de negociações do BCB e mantém só LTN e NTN-F.

Mantém o formato original de cada linha (separador ';', decimal ','). Uso no workflow:
    python scripts/extrair_bcb.py pasta_com_zips saida.csv
"""

import sys
import zipfile
from pathlib import Path

SIGLAS = {"LTN", "NTN-F"}


def _texto(bruto: bytes) -> str:
    try:
        return bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        return bruto.decode("latin-1")


def main(pasta: str, saida: str) -> None:
    cab: str | None = None
    linhas: list[str] = []
    for z in sorted(Path(pasta).glob("*.zip")):
        try:
            arq = zipfile.ZipFile(z)
        except zipfile.BadZipFile:
            print(f"ignorado (não é zip): {z.name}")
            continue
        for nome in arq.namelist():
            texto = _texto(arq.read(nome)).splitlines()
            # o arquivo pode ter linhas de título antes do cabeçalho
            i = next(k for k, ln in enumerate(texto) if ln.upper().startswith("DATA MOV"))
            cab = cab or texto[i]
            col = [c.strip().upper() for c in texto[i].split(";")]
            j = col.index("SIGLA")
            for ln in texto[i + 1 :]:
                partes = ln.split(";")
                if len(partes) > j and partes[j].strip() in SIGLAS:
                    linhas.append(ln)
            print(f"{z.name}/{nome}: {len(texto) - i - 1} linhas")
    if cab is None:
        raise SystemExit("nenhum arquivo do BCB")
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", encoding="utf-8", newline="\n") as f:
        f.write(cab + "\n" + "\n".join(linhas) + "\n")
    print(f"{len(linhas)} linhas de LTN e NTN-F em {saida}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
