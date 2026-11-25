import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from conftest import tabela_titulos
from dicurve.ingest import bcb_titulos as bt
from dicurve.ingest.atualizar import caminho_titulos, gravar_cdi
from dicurve.publish import api
from dicurve.simulado import balanco, carteira

DATAS = [dt.date(2026, 11, 18), dt.date(2026, 11, 19), dt.date(2026, 11, 23), dt.date(2026, 11, 24)]


def _salvar(raiz: Path) -> None:
    bt.para_csv(tabela_titulos(DATAS), caminho_titulos(raiz))
    gravar_cdi(pd.Series([0.1365] * len(DATAS), index=DATAS), raiz)


def test_montar_gera_o_contrato_completo(tmp_path: Path) -> None:
    _salvar(tmp_path)
    arquivos = api.montar(DATAS[-1], tmp_path, pregoes_superficie=3)
    assert set(arquivos) == {
        f"2026-11-24/{n}.json" for n in ("curve", "vertices", "forwards", "risk", "alm", "qa")
    } | {"history/surface-3d.json"}
    for conteudo in arquivos.values():
        assert conteudo["versao"] == api.VERSAO_CONTRATO
        assert conteudo["data_base"] == "2026-11-24"
        assert "ODbL" in conteudo["fonte"]
        json.dumps(conteudo)


def test_titulos_com_variacao_e_origem_dos_vertices(tmp_path: Path) -> None:
    _salvar(tmp_path)
    curva = api.montar(DATAS[-1], tmp_path)["2026-11-24/curve.json"]
    siglas = [t["sigla"] for t in curva["titulos"]]
    assert siglas.count("LTN") == 5 and siglas.count("NTN-F") == 3
    ltns = [t for t in curva["titulos"] if t["sigla"] == "LTN"]
    assert all(t["delta_bps"] == pytest.approx(2.0, abs=0.5) for t in ltns)
    origens = [v["origem"] for v in curva["vertices_curva"]]
    assert origens[0] == "CDI" and origens.count("NTN-F") == 2  # 2035 e 2037 vão além da última LTN


def test_superficie_em_ordem(tmp_path: Path) -> None:
    _salvar(tmp_path)
    sup = api.montar(DATAS[-1], tmp_path, pregoes_superficie=3)["history/surface-3d.json"]
    assert sup["datas"] == [d.isoformat() for d in DATAS[-3:]]
    assert all(len(linha) == len(sup["prazos"]) for linha in sup["taxas"])


def test_risco_e_alm(tmp_path: Path) -> None:
    _salvar(tmp_path)
    arqs = api.montar(DATAS[-1], tmp_path)
    risco, alm = arqs["2026-11-24/risk.json"], arqs["2026-11-24/alm.json"]
    assert sum(risco["key_rate_dv01"].values()) == pytest.approx(risco["metricas"]["dv01"], abs=0.1)
    assert risco["fonte"].startswith("Simulado")
    assert len(risco["posicoes"]) == len(carteira())
    assert risco["cenarios_delta_pv"]["+100 bps"] < 0 < risco["cenarios_delta_pv"]["-100 bps"]
    assert [f["gap"] for f in alm["faixas"]] == [round(f.gap) for f in balanco()]


def test_dia_reprovado_nao_gera_nada(tmp_path: Path) -> None:
    _salvar(tmp_path)
    df = bt.de_csv(caminho_titulos(tmp_path))
    i = df.index[(df["data_base"] == DATAS[-1]) & (df["sigla"] == "LTN")][1]
    df.loc[i, "pu_min"] += 1.0
    bt.para_csv(df, caminho_titulos(tmp_path))
    with pytest.raises(api.DiaReprovadoError):
        api.montar(DATAS[-1], tmp_path)
    destino = tmp_path / "api"
    assert api.main(["--raiz", str(tmp_path), "--destino", str(destino)]) == 1
    assert not destino.exists()


def test_main_escreve_e_aponta_latest(tmp_path: Path) -> None:
    _salvar(tmp_path)
    destino = tmp_path / "api"
    assert api.main(["--raiz", str(tmp_path), "--destino", str(destino)]) == 0
    latest = json.loads((destino / "latest.json").read_text(encoding="utf-8"))
    assert latest["data_base"] == "2026-11-24"
    assert all((destino / rel).exists() for rel in latest["arquivos"])


def test_main_sem_dados(tmp_path: Path) -> None:
    assert api.main(["--raiz", str(tmp_path), "--destino", str(tmp_path / "api")]) == 2


def test_dia_sem_negociacao(tmp_path: Path) -> None:
    _salvar(tmp_path)
    with pytest.raises(ValueError):
        api.montar(dt.date(2026, 11, 25), tmp_path)


def test_superficie_vazia() -> None:
    with pytest.raises(ValueError):
        api.superficie_json([])


def test_podar_mantem_os_mais_recentes(tmp_path: Path) -> None:
    for d in ("2026-11-20", "2026-11-23", "2026-11-24"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "curve.json").write_text("{}")
    (tmp_path / "history").mkdir()
    removidas = api.podar(tmp_path, manter=2)
    assert [p.name for p in removidas] == ["2026-11-20"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-11-23", "2026-11-24", "history"]
