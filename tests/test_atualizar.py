import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from conftest import tabela_titulos
from dicurve.ingest import atualizar, bcb, bcb_titulos


def _fakes(
    monkeypatch: pytest.MonkeyPatch, datas: list[dt.date], cdi_ok: bool = True
) -> list[tuple[int, int]]:
    pedidos: list[tuple[int, int]] = []

    def baixar_mes(ano: int, mes: int) -> pd.DataFrame:
        pedidos.append((ano, mes))
        df = tabela_titulos(datas)
        return df[[(d.year, d.month) == (ano, mes) for d in df["data_base"]]]

    def baixar_serie(codigo: int, inicio: dt.date, fim: dt.date) -> pd.Series:
        if not cdi_ok:
            raise ConnectionError
        return pd.Series([0.1365] * len(datas), index=datas)

    monkeypatch.setattr(bcb_titulos, "baixar_mes", baixar_mes)
    monkeypatch.setattr(bcb, "baixar_serie", baixar_serie)
    return pedidos


DATAS = [dt.date(2026, 10, 30), dt.date(2026, 11, 23), dt.date(2026, 11, 24)]


def test_meses_ate() -> None:
    assert atualizar.meses_ate(dt.date(2026, 1, 15), 3) == [(2025, 11), (2025, 12), (2026, 1)]


def test_atualiza_junta_e_aprova(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos = _fakes(monkeypatch, DATAS)
    assert atualizar.main(["--data", "2026-11-24", "--raiz", str(tmp_path)]) == 0
    assert pedidos == [(2026, 10), (2026, 11)]
    df = bcb_titulos.de_csv(atualizar.caminho_titulos(tmp_path))
    assert bcb_titulos.datas(df) == DATAS
    assert atualizar.ler_cdi(tmp_path).index[-1] == DATAS[-1]
    # rodar de novo não duplica
    assert atualizar.main(["--data", "2026-11-24", "--raiz", str(tmp_path)]) == 0
    assert len(bcb_titulos.de_csv(atualizar.caminho_titulos(tmp_path))) == len(df)


def test_dia_ainda_nao_publicado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fakes(monkeypatch, DATAS)
    assert atualizar.main(["--data", "2026-11-25", "--raiz", str(tmp_path)]) == 3


def test_dados_atrasados_falham(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fakes(monkeypatch, DATAS)
    assert atualizar.main(["--data", "2026-12-04", "--raiz", str(tmp_path), "--meses", "1"]) == 1


def test_sem_cdi_segue_sem_ancora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fakes(monkeypatch, DATAS, cdi_ok=False)
    assert atualizar.main(["--data", "2026-11-24", "--raiz", str(tmp_path)]) == 0
