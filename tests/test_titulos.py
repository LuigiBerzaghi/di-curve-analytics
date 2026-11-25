import datetime as dt
import itertools
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.titulos import (
    CUPOM_NTNF,
    Fluxo,
    Ltn,
    Ntnf,
    bootstrap,
    datas_cupom_ntnf,
    fluxos_ntnf,
    pu_ltn,
    pu_por_curva,
    pu_por_taxa,
    taxa_ltn,
    taxa_por_pu,
)

CAL = CalendarioDU.anbima()
BCB = Path(__file__).parents[1] / "data" / "abertos" / "bcb_prefixados.csv"


def test_cupom_semestral_da_ntnf() -> None:
    assert CUPOM_NTNF == 48.808848


def test_exemplo_ntnf_do_curso_do_tesouro_direto() -> None:
    """ENAP/Tesouro Direto, Tópicos Avançados, cap. 2: 12,98% a.a., 499 DU, PU R$ 953,76.

    O exemplo usa o cupom arredondado em R$ 48,81; com o cupom exato o PU fica R$ 0,005 abaixo.
    """
    fluxos = [Fluxo(120, CUPOM_NTNF), Fluxo(248, CUPOM_NTNF), Fluxo(372, CUPOM_NTNF)]
    fluxos.append(Fluxo(499, CUPOM_NTNF + 1000))
    assert pu_por_taxa(fluxos, 0.1298) == pytest.approx(953.76, abs=0.01)


def test_datas_de_cupom() -> None:
    assert datas_cupom_ntnf(dt.date(2026, 11, 24), dt.date(2029, 1, 1)) == [
        dt.date(2027, 1, 1),
        dt.date(2027, 7, 1),
        dt.date(2028, 1, 1),
        dt.date(2028, 7, 1),
        dt.date(2029, 1, 1),
    ]
    assert datas_cupom_ntnf(dt.date(2029, 1, 1), dt.date(2029, 1, 1)) == []


def test_fluxos_ntnf_somam_principal_no_fim() -> None:
    f = fluxos_ntnf(dt.date(2026, 11, 24), dt.date(2029, 1, 1), CAL)
    assert len(f) == 5
    assert f[-1].valor == pytest.approx(1000 + CUPOM_NTNF)
    assert all(a.du < b.du for a, b in itertools.pairwise(f))
    with pytest.raises(ValueError):
        fluxos_ntnf(dt.date(2026, 11, 24), dt.date(2029, 4, 1), CAL)


@pytest.mark.skipif(not BCB.exists(), reason="recorte do BCB não baixado")
def test_ltn_reproduz_os_pus_do_bcb() -> None:
    """Referência externa: no arquivo do BCB, PU mínimo ↔ taxa máxima de cada LTN negociada."""
    df = pd.read_csv(BCB, sep=";", decimal=",", dtype=str)
    df = df[df["SIGLA"] == "LTN"].dropna(subset=["TAXA MAX"])
    erros = []
    for data, venc, taxa, pu in zip(
        df["DATA MOV"], df["VENCIMENTO"], df["TAXA MAX"], df["PU MIN"], strict=True
    ):
        base = dt.datetime.strptime(data, "%d/%m/%Y").date()
        vencimento = dt.datetime.strptime(venc, "%d/%m/%Y").date()
        du = CAL.contar(base, vencimento)
        erros.append(
            abs(pu_ltn(float(taxa.replace(",", ".")) / 100, du) - float(pu.replace(",", ".")))
        )
    assert len(erros) > 1000
    assert max(erros) < 0.01


@given(st.floats(0.01, 0.40), st.integers(1, 3000))
def test_ltn_ida_e_volta(taxa: float, du: int) -> None:
    assert taxa_ltn(pu_ltn(taxa, du), du) == pytest.approx(taxa, abs=1e-10)


@given(st.floats(0.01, 0.40), st.integers(2, 20))
def test_yield_da_ntnf_ida_e_volta(taxa: float, n_cupons: int) -> None:
    fluxos = [Fluxo(126 * k, CUPOM_NTNF) for k in range(1, n_cupons + 1)]
    fluxos[-1] = Fluxo(fluxos[-1].du, CUPOM_NTNF + 1000)
    assert taxa_por_pu(fluxos, pu_por_taxa(fluxos, taxa)) == pytest.approx(taxa, abs=1e-9)


def _caso(base: dt.date, zero: float) -> tuple[list[Ltn], list[Ntnf]]:
    ltns = [Ltn(v, CAL.contar(base, v), zero) for v in (dt.date(2027, 7, 1), dt.date(2029, 1, 1))]
    ntnfs = []
    for v in (dt.date(2029, 1, 1), dt.date(2031, 1, 1), dt.date(2035, 1, 1)):
        f = tuple(fluxos_ntnf(base, v, CAL))
        ntnfs.append(Ntnf(v, f, pu_por_taxa(f, zero)))
    return ltns, ntnfs


def test_curva_plana_continua_plana() -> None:
    res = bootstrap(*_caso(dt.date(2026, 11, 24), 0.13))
    assert res.curva.taxas == pytest.approx(0.13, abs=1e-10)
    assert list(res.origem.values()).count("NTN-F") == 2
    assert abs(res.erros_ntnf[dt.date(2029, 1, 1)]) < 1e-6  # NTN-F dentro das LTN: só checagem


@settings(max_examples=40, deadline=None)
@given(st.floats(0.05, 0.25), st.floats(-0.03, 0.03), st.floats(-0.03, 0.03))
def test_bootstrap_reprecifica_cada_ntnf(zero: float, d1: float, d2: float) -> None:
    base = dt.date(2026, 11, 24)
    ltns, ntnfs = _caso(base, zero)
    # NTN-F longas com yields diferentes da curva das LTN
    ntnfs = [
        n
        if n.du <= ltns[-1].du
        else Ntnf(n.vencimento, n.fluxos, pu_por_taxa(n.fluxos, zero + (d1 if n.du < 1500 else d2)))
        for n in ntnfs
    ]
    res = bootstrap(ltns, ntnfs)
    for n in ntnfs:
        if n.du > ltns[-1].du:
            assert pu_por_curva(n.fluxos, res.curva) == pytest.approx(n.pu, abs=1e-6)


def test_bootstrap_sem_ltn() -> None:
    with pytest.raises(ValueError):
        bootstrap([], [])
