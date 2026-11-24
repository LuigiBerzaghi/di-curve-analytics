import datetime as dt

import pytest

from dicurve.engine.calendario import (
    CalendarioDU,
    feriados_nacionais,
    pascoa,
    vencimento_di1,
)

CAL = CalendarioDU.anbima()


@pytest.mark.parametrize(
    ("ano", "esperado"),
    [
        (2024, dt.date(2024, 3, 31)),
        (2025, dt.date(2025, 4, 20)),
        (2026, dt.date(2026, 4, 5)),
        (2027, dt.date(2027, 3, 28)),
        (2038, dt.date(2038, 4, 25)),
    ],
)
def test_pascoa_em_datas_conhecidas(ano: int, esperado: dt.date) -> None:
    assert pascoa(ano) == esperado


def test_feriados_de_2026() -> None:
    f = feriados_nacionais(2026)
    assert dt.date(2026, 2, 16) in f  # Carnaval segunda
    assert dt.date(2026, 2, 17) in f  # Carnaval terça
    assert dt.date(2026, 4, 3) in f  # Sexta-feira Santa
    assert dt.date(2026, 6, 4) in f  # Corpus Christi
    assert dt.date(2026, 11, 20) in f  # Consciência Negra
    assert len(f) == 13


def test_consciencia_negra_so_a_partir_de_2024() -> None:
    assert dt.date(2023, 11, 20) not in feriados_nacionais(2023)
    assert dt.date(2024, 11, 20) in feriados_nacionais(2024)


def test_data_base_antiga_nao_desconta_o_20_de_novembro() -> None:
    # Antes de 26/12/2023 o 20/11 não estava na lista: o DU calculado naquela época
    # contava 20/11/2024 como dia útil. A partir da transição, não conta mais.
    fim = dt.date(2024, 12, 2)
    antes = CAL.contar(dt.date(2023, 12, 22), fim)
    depois = CAL.contar(dt.date(2023, 12, 26), fim)
    dias_corridos_uteis_entre = CAL.contar(dt.date(2023, 12, 22), dt.date(2023, 12, 26))
    assert antes - dias_corridos_uteis_entre == depois + 1


def test_sem_vigencia_usa_sempre_a_lista_atual() -> None:
    cal = CalendarioDU.anbima(considerar_vigencia=False)
    assert not cal.eh_dia_util(dt.date(2024, 11, 20))
    assert (
        cal.contar(dt.date(2023, 12, 22), dt.date(2024, 12, 2))
        == CAL.contar(dt.date(2023, 12, 22), dt.date(2024, 12, 2)) - 1
    )


def test_transicao_exige_as_duas_informacoes() -> None:
    with pytest.raises(ValueError):
        CalendarioDU([], feriados_anteriores=[])


def test_contagem_inclui_inicio_e_exclui_fim() -> None:
    seg, ter = dt.date(2026, 11, 23), dt.date(2026, 11, 24)
    assert CAL.contar(seg, ter) == 1
    assert CAL.contar(seg, seg) == 0
    assert CAL.contar(ter, seg) == -1


def test_contagem_pula_fim_de_semana_e_feriado() -> None:
    # 19/11/2026 é quinta; 20/11 é feriado; 21 e 22 são fim de semana
    assert CAL.contar(dt.date(2026, 11, 19), dt.date(2026, 11, 23)) == 1


def test_du_ate_o_vencimento_do_f27() -> None:
    assert CAL.contar(dt.date(2026, 11, 16), dt.date(2027, 1, 4)) == 32


def test_ajustes_de_data() -> None:
    sabado = dt.date(2026, 11, 21)
    assert not CAL.eh_dia_util(sabado)
    assert CAL.dia_util_seguinte(sabado) == dt.date(2026, 11, 23)
    assert CAL.dia_util_anterior(sabado) == dt.date(2026, 11, 19)
    assert CAL.deslocar(dt.date(2026, 11, 19), 1) == dt.date(2026, 11, 23)


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("DI1F27", dt.date(2027, 1, 4)),
        ("F28", dt.date(2028, 1, 3)),
        ("di1n26", dt.date(2026, 7, 1)),
        ("DI1F29", dt.date(2029, 1, 2)),
    ],
)
def test_vencimento_di1(codigo: str, esperado: dt.date) -> None:
    assert vencimento_di1(codigo, CAL) == esperado


@pytest.mark.parametrize("codigo", ["DI1A27", "X2", "DI1F2X", ""])
def test_vencimento_di1_rejeita_codigo_invalido(codigo: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        vencimento_di1(codigo, CAL)
