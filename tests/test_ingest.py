import datetime as dt
import itertools
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import DATA_BASE, registros_pyield
from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import armazenamento, atualizar, b3_di1, backfill, bcb

# ---------- B3 ----------


def test_normalizar_renomeia_e_ordena(ajustes: pd.DataFrame) -> None:
    assert list(ajustes.columns) == b3_di1.ORDEM
    assert ajustes["vencimento"].is_monotonic_increasing
    assert ajustes.loc[0, "codigo"] == "DI1F27"
    assert ajustes.loc[0, "du_b3"] == 28
    assert isinstance(ajustes.loc[0, "data_base"], dt.date)


def test_normalizar_vazio() -> None:
    assert b3_di1.normalizar([]).empty


def test_curva_de_ajustes_passa_pelos_contratos(ajustes: pd.DataFrame) -> None:
    curva = b3_di1.curva_de_ajustes(ajustes)
    assert len(curva) == len(ajustes)
    assert curva.taxa(float(ajustes.loc[3, "du_b3"])) == pytest.approx(
        ajustes.loc[3, "taxa_ajuste"]
    )


def test_curva_exige_uma_data(ajustes: pd.DataFrame) -> None:
    outra = ajustes.copy()
    outra["data_base"] = dt.date(2026, 11, 24)
    with pytest.raises(ValueError, match="única data-base"):
        b3_di1.curva_de_ajustes(pd.concat([ajustes, outra]))


# ---------- BCB ----------


def test_janelas_de_ate_dez_anos() -> None:
    j = bcb.janelas(dt.date(2000, 1, 1), dt.date(2025, 6, 30))
    assert j[0] == (dt.date(2000, 1, 1), dt.date(2009, 12, 31))
    assert j[-1][1] == dt.date(2025, 6, 30)
    assert len(j) == 3
    for (_, fim), (inicio, _) in itertools.pairwise(j):
        assert inicio == fim + dt.timedelta(days=1)


def test_janela_comecando_em_29_de_fevereiro() -> None:
    j = bcb.janelas(dt.date(2016, 2, 29), dt.date(2030, 1, 1))
    assert j[0][1] == dt.date(2026, 2, 27)


def test_janela_invalida() -> None:
    with pytest.raises(ValueError):
        bcb.janelas(dt.date(2025, 1, 2), dt.date(2025, 1, 1))


def test_parse_sgs_converte_para_fracao() -> None:
    s = bcb.parse_sgs(
        [{"data": "19/11/2026", "valor": "14.90"}, {"data": "18/11/2026", "valor": "14,88"}]
    )
    assert list(s.index) == [dt.date(2026, 11, 18), dt.date(2026, 11, 19)]
    assert s.iloc[-1] == pytest.approx(0.149)


class _Resposta:
    def __init__(self, payload: list[dict[str, str]]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


def test_baixar_serie_divide_em_janelas_e_junta() -> None:
    chamadas: list[dict[str, Any]] = []

    def falso_get(url: str, params: dict[str, str], timeout: float) -> _Resposta:
        chamadas.append({"url": url, **params})
        return _Resposta([{"data": params["dataInicial"], "valor": "10.00"}])

    s = bcb.baixar_serie(432, dt.date(2000, 1, 1), dt.date(2025, 1, 1), get=falso_get)
    assert len(chamadas) == 3
    assert "bcdata.sgs.432" in chamadas[0]["url"]
    assert chamadas[0]["dataInicial"] == "01/01/2000"
    assert len(s) == 3 and s.iloc[0] == pytest.approx(0.10)


# ---------- armazenamento ----------


def test_salvar_e_ler(tmp_path: Path, ajustes: pd.DataFrame) -> None:
    destino = armazenamento.salvar(ajustes, "b3_di1", DATA_BASE, tmp_path)
    assert destino == tmp_path / "b3_di1" / "2026-11-23.parquet"
    lido = armazenamento.ler("b3_di1", DATA_BASE, tmp_path)
    pd.testing.assert_frame_equal(lido, ajustes, check_dtype=False)
    assert armazenamento.datas_salvas("b3_di1", tmp_path) == [DATA_BASE]
    assert not list(tmp_path.rglob("*.tmp"))


def test_fonte_invalida_nao_escapa_da_pasta(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        armazenamento.caminho("../fora", DATA_BASE, tmp_path)


def test_datas_salvas_sem_pasta(tmp_path: Path) -> None:
    assert armazenamento.datas_salvas("nada", tmp_path) == []


# ---------- comando atualizar (sem rede) ----------


def _falso_baixar(registros: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    def baixar(datas: list[dt.date]) -> pd.DataFrame:
        ant = registros_pyield(datas[0])
        return b3_di1.normalizar(ant + registros)

    return baixar


def test_atualizar_aprova_e_salva(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(b3_di1, "baixar_ajustes", _falso_baixar(registros_pyield()))
    codigo = atualizar.main(["--data", "2026-11-23", "--raiz", str(tmp_path), "--sem-bcb"])
    assert codigo == 0
    assert armazenamento.datas_salvas("b3_di1", tmp_path) == [dt.date(2026, 11, 19), DATA_BASE]


def test_atualizar_reprova_dado_ruim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ruins = registros_pyield()
    ruins[2]["preco_ajuste"] += 5.0
    monkeypatch.setattr(b3_di1, "baixar_ajustes", _falso_baixar(ruins))
    assert atualizar.main(["--data", "2026-11-23", "--raiz", str(tmp_path), "--sem-bcb"]) == 1


def test_atualizar_recusa_dia_nao_util(tmp_path: Path) -> None:
    assert atualizar.main(["--data", "2026-11-20", "--raiz", str(tmp_path), "--sem-bcb"]) == 2


# ---------- backfill (sem rede) ----------


def test_pregoes_termina_no_ultimo_dia_util(cal: CalendarioDU) -> None:
    datas = backfill.pregoes(cal, dt.date(2026, 11, 22), 3)  # domingo
    assert datas == [dt.date(2026, 11, 17), dt.date(2026, 11, 18), dt.date(2026, 11, 19)]
    assert all(cal.eh_dia_util(d) for d in datas)
    with pytest.raises(ValueError):
        backfill.pregoes(cal, DATA_BASE, 0)


def test_sem_pregao_em_24_e_31_de_dezembro(cal: CalendarioDU) -> None:
    assert cal.eh_dia_util(dt.date(2025, 12, 24))  # conta como DU...
    assert not b3_di1.tem_pregao(cal, dt.date(2025, 12, 24))  # ...mas a B3 não abre
    assert b3_di1.pregao_anterior(cal, dt.date(2026, 1, 2)) == dt.date(2025, 12, 30)
    datas = backfill.pregoes(cal, dt.date(2026, 1, 2), 5)
    assert dt.date(2025, 12, 31) not in datas and dt.date(2025, 12, 24) not in datas
    assert datas[-2:] == [dt.date(2025, 12, 30), dt.date(2026, 1, 2)]


def test_atualizar_recusa_dia_sem_pregao(tmp_path: Path) -> None:
    assert atualizar.main(["--data", "2025-12-31", "--raiz", str(tmp_path), "--sem-bcb"]) == 2


def test_backfill_baixa_so_o_que_falta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[list[dt.date]] = []

    def baixar(datas: list[dt.date]) -> pd.DataFrame:
        pedidos.append(list(datas))
        return b3_di1.normalizar([r for d in datas for r in registros_pyield(d)])

    monkeypatch.setattr(b3_di1, "baixar_ajustes", baixar)
    args = ["--pregoes", "5", "--ate", "2026-11-23", "--lote", "2", "--raiz", str(tmp_path)]
    assert backfill.main(args) == 0
    assert [len(p) for p in pedidos] == [2, 2, 1]
    assert len(armazenamento.datas_salvas("b3_di1", tmp_path)) == 5
    pedidos.clear()
    assert backfill.main(args) == 0
    assert pedidos == []


def test_backfill_aponta_dia_sem_dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(b3_di1, "baixar_ajustes", lambda datas: b3_di1.normalizar([]))
    args = ["--pregoes", "2", "--ate", "2026-11-23", "--raiz", str(tmp_path)]
    assert backfill.main(args) == 1
