"""Calendário de dias úteis com os feriados nacionais (padrão ANBIMA).

Os feriados são calculados por regra, sem arquivo externo: datas fixas mais os feriados
móveis derivados da Páscoa. O resultado é conferido nos testes contra o calendário
ANBIMA do pacote ``bizdays`` e contra o PYield.

Convenção de contagem: ``contar(inicio, fim)`` conta os dias úteis no intervalo
``[inicio, fim)``, ou seja, inclui a data inicial e exclui a final. É a mesma convenção
usada pelo mercado para o DU entre a data-base e o vencimento.

Vigência dos feriados: o Dia da Consciência Negra (20/11) virou feriado nacional no fim
de 2023. Uma contagem feita antes disso não descontava esse dia, nem para vencimentos
futuros. Por isso a lista de feriados usada é a que estava **vigente na data inicial**
da contagem (a data-base), com transição em 26/12/2023, a mesma convenção do PYield.
Sem essa regra, os PUs históricos não batem com os da B3.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import cast

import numpy as np

#: Feriados nacionais de data fixa: (mês, dia) -> nome.
FERIADOS_FIXOS: dict[tuple[int, int], str] = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (12, 25): "Natal",
}

#: Primeiro ano em que o Dia da Consciência Negra (20/11) é feriado nacional.
ANO_CONSCIENCIA_NEGRA = 2024

#: Data-base a partir da qual a lista de feriados inclui o 20/11 (convenção do PYield).
DATA_TRANSICAO_CONSCIENCIA_NEGRA = dt.date(2023, 12, 26)

#: Letra do mês nos códigos de vencimento da B3.
LETRAS_MES: dict[str, int] = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}


def pascoa(ano: int) -> dt.date:
    """Domingo de Páscoa no calendário gregoriano (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    mes, dia = divmod(h + el - 7 * m + 114, 31)
    return dt.date(ano, mes, dia + 1)


def feriados_nacionais(ano: int) -> dict[dt.date, str]:
    """Feriados nacionais de um ano: data -> nome."""
    feriados = {dt.date(ano, m, d): nome for (m, d), nome in FERIADOS_FIXOS.items()}
    if ano >= ANO_CONSCIENCIA_NEGRA:
        feriados[dt.date(ano, 11, 20)] = "Dia Nacional de Zumbi e da Consciência Negra"
    p = pascoa(ano)
    feriados[p - dt.timedelta(days=48)] = "Carnaval (segunda-feira)"
    feriados[p - dt.timedelta(days=47)] = "Carnaval (terça-feira)"
    feriados[p - dt.timedelta(days=2)] = "Sexta-feira Santa"
    feriados[p + dt.timedelta(days=60)] = "Corpus Christi"
    return dict(sorted(feriados.items()))


def _d64(data: dt.date) -> np.datetime64:
    return np.datetime64(data, "D")


def _para_date(valor: np.datetime64) -> dt.date:
    return cast(dt.date, valor.astype(dt.date))


def _vetor_datas(datas: Iterable[dt.date]) -> np.ndarray:
    return np.array(sorted(set(datas)), dtype="datetime64[D]")


class CalendarioDU:
    """Calendário de dias úteis: fins de semana e feriados não são dias úteis.

    Opcionalmente aceita uma lista de feriados anterior e a data de transição entre as
    duas: operações a partir de uma data anterior à transição usam a lista anterior.
    """

    def __init__(
        self,
        feriados: Iterable[dt.date],
        *,
        feriados_anteriores: Iterable[dt.date] | None = None,
        data_transicao: dt.date | None = None,
    ) -> None:
        if (feriados_anteriores is None) != (data_transicao is None):
            raise ValueError("informe feriados_anteriores e data_transicao juntos")
        self._atuais = _vetor_datas(feriados)
        self._anteriores = (
            None if feriados_anteriores is None else _vetor_datas(feriados_anteriores)
        )
        self._transicao = data_transicao

    @classmethod
    def anbima(
        cls, ano_inicial: int = 1990, ano_final: int = 2100, *, considerar_vigencia: bool = True
    ) -> CalendarioDU:
        """Feriados nacionais entre ``ano_inicial`` e ``ano_final``.

        Com ``considerar_vigencia=False``, usa a lista atual para qualquer data-base
        (equivale ao calendário ANBIMA do pacote ``bizdays``).
        """
        atuais: list[dt.date] = []
        for ano in range(ano_inicial, ano_final + 1):
            atuais.extend(feriados_nacionais(ano))
        if not considerar_vigencia:
            return cls(atuais)
        anteriores = [d for d in atuais if (d.month, d.day) != (11, 20)]
        return cls(
            atuais,
            feriados_anteriores=anteriores,
            data_transicao=DATA_TRANSICAO_CONSCIENCIA_NEGRA,
        )

    def _vigentes(self, data: dt.date) -> np.ndarray:
        if self._anteriores is not None and self._transicao and data < self._transicao:
            return self._anteriores
        return self._atuais

    @property
    def feriados(self) -> list[dt.date]:
        """Lista atual de feriados."""
        return [_para_date(d) for d in self._atuais]

    def eh_dia_util(self, data: dt.date) -> bool:
        return bool(np.is_busday(_d64(data), holidays=self._vigentes(data)))

    def contar(self, inicio: dt.date, fim: dt.date) -> int:
        """Dias úteis em ``[inicio, fim)``, com os feriados vigentes em ``inicio``.

        Negativo se ``fim`` vier antes de ``inicio``.
        """
        feriados = self._vigentes(inicio)
        return int(np.busday_count(_d64(inicio), _d64(fim), holidays=feriados))

    def deslocar(self, data: dt.date, dias_uteis: int) -> dt.date:
        """Anda ``dias_uteis`` dias úteis a partir de ``data`` (ajustada para dia útil)."""
        feriados = self._vigentes(data)
        resultado = np.busday_offset(_d64(data), dias_uteis, roll="forward", holidays=feriados)
        return _para_date(resultado)

    def dia_util_seguinte(self, data: dt.date) -> dt.date:
        """A própria data, se for dia útil; senão, o próximo dia útil."""
        return self.deslocar(data, 0)

    def dia_util_anterior(self, data: dt.date) -> dt.date:
        """A própria data, se for dia útil; senão, o dia útil anterior."""
        feriados = self._vigentes(data)
        resultado = np.busday_offset(_d64(data), 0, roll="backward", holidays=feriados)
        return _para_date(resultado)


def vencimento_di1(codigo: str, calendario: CalendarioDU) -> dt.date:
    """Data de vencimento de um contrato DI1: primeiro dia útil do mês do código.

    Aceita ``"DI1F27"`` ou ``"F27"``.
    """
    sufixo = codigo.upper().removeprefix("DI1")
    if len(sufixo) != 3 or sufixo[0] not in LETRAS_MES or not sufixo[1:].isdigit():
        raise ValueError(f"Código de DI1 inválido: {codigo!r}")
    mes = LETRAS_MES[sufixo[0]]
    ano = 2000 + int(sufixo[1:])
    return calendario.dia_util_seguinte(dt.date(ano, mes, 1))
