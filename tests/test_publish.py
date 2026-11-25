import datetime as dt
import json
from pathlib import Path

import pytest

from conftest import CAL, registros_pyield
from dicurve.ingest import armazenamento, b3_di1
from dicurve.publish import api
from dicurve.simulado import balanco, carteira

DATAS = [dt.date(2026, 11, 17), dt.date(2026, 11, 18), dt.date(2026, 11, 19), dt.date(2026, 11, 23)]


def _salvar(raiz: Path, datas: list[dt.date] = DATAS) -> None:
    for i, d in enumerate(datas):
        df = b3_di1.normalizar(
            registros_pyield(d, taxa=lambda du, i=i: 0.137 + du * 7e-6 + i * 5e-4)
        )
        armazenamento.salvar(df, "b3_di1", d, raiz)


def test_montar_gera_o_contrato_completo(tmp_path: Path) -> None:
    _salvar(tmp_path)
    arquivos = api.montar(DATAS[-1], tmp_path, cal=CAL, pregoes_superficie=3)
    assert set(arquivos) == {
        f"2026-11-23/{n}.json" for n in ("curve", "vertices", "forwards", "risk", "alm", "qa")
    } | {"history/surface-3d.json"}
    for conteudo in arquivos.values():
        assert conteudo["versao"] == api.VERSAO_CONTRATO
        assert conteudo["data_base"] == "2026-11-23"
        json.dumps(conteudo)  # serializável


def test_curva_traz_variacao_contra_o_pregao_anterior(tmp_path: Path) -> None:
    _salvar(tmp_path)
    curva = api.montar(DATAS[-1], tmp_path, cal=CAL)["2026-11-23/curve.json"]
    assert all(c["delta_bps"] == pytest.approx(5.0, abs=0.5) for c in curva["contratos"])
    hoje = armazenamento.ler("b3_di1", DATAS[-1], tmp_path)
    for c, pu_b3 in zip(curva["contratos"], hoje["pu_ajuste"], strict=True):
        assert c["pu"] == pytest.approx(pu_b3, abs=0.01)


def test_superficie_em_ordem_e_com_todos_os_prazos(tmp_path: Path) -> None:
    _salvar(tmp_path)
    sup = api.montar(DATAS[-1], tmp_path, cal=CAL, pregoes_superficie=3)["history/surface-3d.json"]
    assert sup["datas"] == [d.isoformat() for d in DATAS[-3:]]
    assert len(sup["taxas"]) == 3 and all(
        len(linha) == len(sup["prazos"]) for linha in sup["taxas"]
    )


def test_key_rate_soma_o_dv01_da_carteira(tmp_path: Path) -> None:
    _salvar(tmp_path)
    risco = api.montar(DATAS[-1], tmp_path, cal=CAL)["2026-11-23/risk.json"]
    assert sum(risco["key_rate_dv01"].values()) == pytest.approx(risco["metricas"]["dv01"], abs=0.1)
    assert risco["fonte"].startswith("Simulado")
    assert len(risco["posicoes"]) == len(carteira())
    # dado (PV > 0 domina): alta de taxa perde, queda ganha
    assert risco["cenarios_delta_pv"]["+100 bps"] < 0 < risco["cenarios_delta_pv"]["-100 bps"]


def test_alm_com_gaps_do_balanco(tmp_path: Path) -> None:
    _salvar(tmp_path)
    alm = api.montar(DATAS[-1], tmp_path, cal=CAL)["2026-11-23/alm.json"]
    assert [f["gap"] for f in alm["faixas"]] == [round(f.gap) for f in balanco()]
    assert [c["bps"] for c in alm["choques"]] == list(api.CHOQUES_PARALELOS)


def test_dia_reprovado_nao_gera_nada(tmp_path: Path) -> None:
    _salvar(tmp_path)
    ruim = armazenamento.ler("b3_di1", DATAS[-1], tmp_path)
    ruim.loc[0, "pu_ajuste"] += 1.0
    armazenamento.salvar(ruim, "b3_di1", DATAS[-1], tmp_path)
    with pytest.raises(api.DiaReprovadoError):
        api.montar(DATAS[-1], tmp_path, cal=CAL)
    destino = tmp_path / "api"
    assert (
        api.main(["--data", "2026-11-23", "--raiz", str(tmp_path), "--destino", str(destino)]) == 1
    )
    assert not destino.exists()


def test_main_escreve_e_aponta_latest(tmp_path: Path) -> None:
    _salvar(tmp_path)
    destino = tmp_path / "api"
    assert api.main(["--raiz", str(tmp_path), "--destino", str(destino)]) == 0
    latest = json.loads((destino / "latest.json").read_text(encoding="utf-8"))
    assert latest["data_base"] == "2026-11-23"
    assert all((destino / rel).exists() for rel in latest["arquivos"])


def test_main_sem_dados(tmp_path: Path) -> None:
    assert api.main(["--raiz", str(tmp_path), "--destino", str(tmp_path / "api")]) == 2


def test_superficie_vazia() -> None:
    with pytest.raises(ValueError):
        api.superficie_json([])
