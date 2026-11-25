import datetime as dt
import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import CAL, tabela_titulos
from dicurve.engine.titulos import pu_por_curva
from dicurve.ingest import bcb_titulos as bt

CSV = """DATA MOV;SIGLA;CODIGO;CODIGO ISIN;EMISSAO;VENCIMENTO;NUM DE OPER;QUANT NEGOCIADA;VALOR NEGOCIADO;PU MIN;PU MED;PU MAX;PU LASTRO;VALOR PAR;TAXA MIN;TAXA MED;TAXA MAX;NUM OPER COM CORRETAGEM;QUANT NEG COM CORRETAGEM
24/11/2026;LTN;100000;BRSTNCLTN1;01/01/2024;01/04/2027;18;603566;;955,9;956,053964;956,2;955,0;1000,0;13,85;13,9026;13,95;0;0
24/11/2026;NTN-F;950199;BRSTNCNTF1;05/01/2018;01/01/2029;20;333406;;950,0;953,893229;956,0;950,0;1000,0;;;;0;0
24/11/2026;NTN-F;950198;BRSTNCNTF2;01/10/2019;01/01/2029;1;10;;642,0;642,799662;643,0;640,0;1000,0;;;;0;0
24/11/2026;LFT;210100;BRSTNCLF1;01/01/2024;01/03/2027;5;100;;17000,0;17001,0;17002,0;17000,0;17000,0;0,01;0,02;0,03;0;0
24/11/2026;LTN;100000;BRSTNCLTN2;01/01/2024;01/07/2027;1;5;;;;;;1000,0;;;;1;5
"""


def test_ler_csv_filtra_e_converte() -> None:
    df = bt.ler_csv("Título qualquer\n" + CSV)
    assert list(df.columns) == bt.ORDEM
    assert list(df["sigla"]) == ["LTN", "NTN-F"]  # sem strip (950198), LFT e linha sem PU
    assert df.loc[0, "taxa_med"] == pytest.approx(0.139026)
    assert df.loc[0, "pu_med"] == pytest.approx(956.053964)
    assert pd.isna(df.loc[1, "taxa_med"])
    assert df.loc[0, "data_base"] == dt.date(2026, 11, 24)


def test_ler_csv_sem_cabecalho() -> None:
    assert bt.ler_csv("nada aqui").empty


def _zip(texto: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("NegE202611.CSV", texto.encode("latin-1"))
    return buf.getvalue()


def test_baixar_mes_com_get_falso() -> None:
    urls = []

    class Resp:
        content = _zip(CSV)

        def raise_for_status(self) -> None:
            return None

    def get(url: str, timeout: float) -> Any:
        urls.append(url)
        return Resp()

    df = bt.baixar_mes(2026, 11, get=get)
    assert urls == ["https://www4.bcb.gov.br/pom/demab/negociacoes/download/NegE202611.ZIP"]
    assert len(df) == 2


def test_juntar_fica_com_o_mais_recente() -> None:
    a = bt.ler_csv(CSV)
    b = a.copy()
    b["pu_med"] += 1
    j = bt.juntar(a, b)
    assert len(j) == 2 and j["pu_med"].tolist() == b["pu_med"].tolist()


def test_csv_ida_e_volta(tmp_path: Path) -> None:
    df = tabela_titulos([dt.date(2026, 11, 24)])
    bt.para_csv(df, tmp_path / "t.csv")
    pd.testing.assert_frame_equal(bt.de_csv(tmp_path / "t.csv"), df, check_dtype=False)


def test_ltn_sem_taxa_usa_o_pu() -> None:
    df = tabela_titulos([dt.date(2026, 11, 24)])
    esperado = bt.titulos_do_dia(df, dt.date(2026, 11, 24), CAL)[0][0].taxa
    df.loc[0, "taxa_med"] = None
    assert bt.titulos_do_dia(df, dt.date(2026, 11, 24), CAL)[0][0].taxa == pytest.approx(
        esperado, abs=1e-9
    )


def test_curva_do_dia_reprecifica_as_ntnf_longas_e_ancora_no_cdi() -> None:
    d = dt.date(2026, 11, 24)
    df = tabela_titulos([d])
    res = bt.curva_do_dia(df, d, CAL, cdi=0.1365)
    assert res.origem[1] == "CDI" and res.curva.taxa(1.0) == pytest.approx(0.1365)
    ltns, ntnfs = bt.titulos_do_dia(df, d, CAL)
    longas = [n for n in ntnfs if n.du > max(x.du for x in ltns)]
    assert len(longas) == 2
    for n in longas:
        assert pu_por_curva(n.fluxos, res.curva) == pytest.approx(n.pu, abs=1e-6)
