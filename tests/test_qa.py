import pandas as pd
import pytest

from conftest import registros_pyield
from dicurve.engine.calendario import CalendarioDU
from dicurve.ingest import b3_di1
from dicurve.qa.verificacoes import aprovado, relatorio, verificar_di1


def _por_nome(
    df: pd.DataFrame, cal: CalendarioDU, anterior: pd.DataFrame | None = None
) -> dict[str, bool]:
    return {r.nome: r.ok for r in verificar_di1(df, cal, anterior)}


def test_dados_consistentes_passam_em_tudo(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    res = verificar_di1(ajustes, cal, ajustes)
    assert all(r.ok for r in res), relatorio(res)
    assert aprovado(res)
    assert {r.nome for r in res} == {
        "vertices_completos",
        "banda_taxa",
        "variacao_diaria",
        "dias_uteis",
        "pu_recalculado",
        "sem_arbitragem",
    }


def test_contrato_sem_ajuste(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    ajustes.loc[2, "taxa_ajuste"] = None
    assert _por_nome(ajustes, cal)["vertices_completos"] is False


def test_taxa_fora_da_banda(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    ajustes.loc[0, "taxa_ajuste"] = 0.45
    assert _por_nome(ajustes, cal)["banda_taxa"] is False


def test_du_diferente_da_b3(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    ajustes.loc[1, "du_b3"] += 1
    assert _por_nome(ajustes, cal)["dias_uteis"] is False


def test_pu_fora_da_tolerancia(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    ajustes.loc[3, "pu_ajuste"] += 0.02
    res = verificar_di1(ajustes, cal)
    assert {r.nome: r.ok for r in res}["pu_recalculado"] is False
    assert not aprovado(res)


def test_curva_com_arbitragem() -> None:
    registros = registros_pyield(taxa=lambda du: 0.20 if du < 300 else 0.05)
    df = b3_di1.normalizar(registros)
    assert _por_nome(df, CalendarioDU.anbima())["sem_arbitragem"] is False


def test_variacao_grande_e_so_alerta(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    ontem = ajustes.copy()
    ontem["taxa_ajuste"] -= 0.0060  # 60 bps
    ontem["data_base"] = pd.Timestamp("2026-11-19").date()
    res = verificar_di1(ajustes, cal, ontem)
    var = next(r for r in res if r.nome == "variacao_diaria")
    assert var.ok is False and var.gravidade == "alerta"
    assert aprovado(res)  # alerta não bloqueia


def test_sem_dados() -> None:
    res = verificar_di1(b3_di1.normalizar([]), CalendarioDU.anbima())
    assert not aprovado(res)


def test_exige_uma_data(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    outra = ajustes.copy()
    outra["data_base"] = pd.Timestamp("2026-11-24").date()
    with pytest.raises(ValueError):
        verificar_di1(pd.concat([ajustes, outra]), cal)


def test_relatorio_legivel(ajustes: pd.DataFrame, cal: CalendarioDU) -> None:
    texto = relatorio(verificar_di1(ajustes, cal), "DI1 teste")
    assert texto.startswith("DI1 teste") and "APROVADO" in texto
