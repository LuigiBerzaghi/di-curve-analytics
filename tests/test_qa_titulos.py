import datetime as dt

from conftest import CAL, tabela_titulos
from dicurve.ingest import bcb_titulos as bt
from dicurve.qa.titulos import verificar_titulos
from dicurve.qa.verificacoes import aprovado

D0, D1 = dt.date(2026, 11, 23), dt.date(2026, 11, 24)


def _verificar(df, ant=True):  # type: ignore[no-untyped-def]
    res = bt.curva_do_dia(df, D1, CAL, 0.1365)
    anterior = bt.curva_do_dia(df, D0, CAL, 0.1365).curva if ant else None
    return {r.nome: r for r in verificar_titulos(df, D1, CAL, res, anterior)}


def test_dados_consistentes_passam() -> None:
    r = _verificar(tabela_titulos([D0, D1]))
    assert all(x.ok for x in r.values()), [x.detalhe for x in r.values()]
    assert aprovado(list(r.values()))


def test_poucas_ltn_reprova() -> None:
    df = tabela_titulos([D0, D1])
    df = df[
        ~(
            (df["data_base"] == D1)
            & (df["sigla"] == "LTN")
            & (df["vencimento"] > dt.date(2028, 1, 1))
        )
    ]
    assert _verificar(df)["titulos_suficientes"].ok is False


def test_taxa_fora_da_banda() -> None:
    df = tabela_titulos([D0, D1])
    i = df.index[(df["data_base"] == D1) & (df["sigla"] == "LTN")][0]
    df.loc[i, ["taxa_med", "taxa_min", "taxa_max"]] = 0.45
    assert _verificar(df)["banda_taxa"].ok is False


def test_pu_que_nao_bate_com_a_taxa() -> None:
    df = tabela_titulos([D0, D1])
    i = df.index[(df["data_base"] == D1) & (df["sigla"] == "LTN")][2]
    df.loc[i, "pu_min"] += 0.5
    assert _verificar(df)["pu_recalculado"].ok is False


def test_curva_invertida_demais_tem_forward_negativa() -> None:
    df = tabela_titulos([D0, D1])
    i = df.index[(df["data_base"] == D1) & (df["sigla"] == "LTN")]
    df.loc[i[0], ["taxa_med", "taxa_min", "taxa_max"]] = 0.28  # LTN curta muito acima das demais
    df.loc[i[1], ["taxa_med", "taxa_min", "taxa_max"]] = 0.05
    assert _verificar(df)["sem_arbitragem"].ok is False


def test_ntnf_descolada_e_so_alerta() -> None:
    df = tabela_titulos([D0, D1])
    i = df.index[
        (df["data_base"] == D1)
        & (df["sigla"] == "NTN-F")
        & (df["vencimento"] == dt.date(2029, 1, 1))
    ][0]
    df.loc[i, "pu_med"] -= 15  # ~+60 bps na yield
    r = _verificar(df)
    assert r["ntnf_coerente"].ok is False and r["ntnf_coerente"].gravidade == "alerta"
    assert aprovado(list(r.values()))


def test_variacao_grande_e_so_alerta() -> None:
    df = tabela_titulos([D0, D1], zero=lambda du: 0.14)
    df.loc[df["data_base"] == D0, ["taxa_med", "taxa_min", "taxa_max"]] -= 0.008
    r = _verificar(df)
    assert r["variacao_diaria"].ok is False and aprovado(list(r.values()))
    assert _verificar(df, ant=False)["variacao_diaria"].ok is True
