"""Títulos públicos prefixados: LTN e NTN-F, e o bootstrapping da curva pré.

- LTN: zero cupom, R$ 1.000 no vencimento. PU = 1000 / (1 + taxa)^(DU/252).
- NTN-F: cupom de 10% a.a. pago em 1º/jan e 1º/jul (R$ 48,808848 por semestre) e
  R$ 1.000 no vencimento. O PU é a soma dos fluxos descontados pela mesma taxa.

Bootstrapping: as LTN dão a taxa zero diretamente em cada vencimento. Para cada NTN-F
que vence depois da última LTN, procura-se a taxa zero no seu vencimento que faz a curva
(flat-forward) reprecificar o PU negociado. Os cupons anteriores usam a curva já montada.

Funções puras, sem I/O.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from dicurve import DIAS_UTEIS_ANO
from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.curva import CurvaPre

FACE_TPF = 1000.0
CUPOM_NTNF_ANUAL = 0.10
#: Cupom semestral da NTN-F, arredondado em 6 casas como na metodologia do Tesouro.
CUPOM_NTNF = round(FACE_TPF * ((1 + CUPOM_NTNF_ANUAL) ** 0.5 - 1), 6)


@dataclass(frozen=True)
class Fluxo:
    du: int
    valor: float


def pu_ltn(taxa: float, du: float) -> float:
    return float(FACE_TPF / (1 + taxa) ** (du / DIAS_UTEIS_ANO))


def taxa_ltn(pu: float, du: float) -> float:
    if du <= 0 or pu <= 0:
        raise ValueError("du e pu precisam ser positivos")
    return float((FACE_TPF / pu) ** (DIAS_UTEIS_ANO / du) - 1)


def datas_cupom_ntnf(data_base: dt.date, vencimento: dt.date) -> list[dt.date]:
    """Datas de cupom (1º/jan e 1º/jul) depois da data-base, até o vencimento."""
    if vencimento <= data_base:
        return []
    datas = []
    ano, mes = vencimento.year, vencimento.month
    d = vencimento
    while d > data_base:
        datas.append(d)
        mes -= 6
        if mes <= 0:
            mes += 12
            ano -= 1
        d = dt.date(ano, mes, 1)
    return sorted(datas)


def fluxos_ntnf(data_base: dt.date, vencimento: dt.date, cal: CalendarioDU) -> list[Fluxo]:
    """Cupons e principal da NTN-F a partir da data-base, com o DU de cada pagamento."""
    if (vencimento.month, vencimento.day) not in {(1, 1), (7, 1)}:
        raise ValueError("NTN-F vence em 1º/jan ou 1º/jul")
    datas = datas_cupom_ntnf(data_base, vencimento)
    fluxos = [Fluxo(cal.contar(data_base, d), CUPOM_NTNF) for d in datas]
    if fluxos:
        ultimo = fluxos[-1]
        fluxos[-1] = Fluxo(ultimo.du, ultimo.valor + FACE_TPF)
    return [f for f in fluxos if f.du > 0]


def pu_por_taxa(fluxos: Sequence[Fluxo], taxa: float) -> float:
    """PU com todos os fluxos descontados pela mesma taxa (yield)."""
    return float(sum(f.valor / (1 + taxa) ** (f.du / DIAS_UTEIS_ANO) for f in fluxos))


def pu_por_curva(fluxos: Sequence[Fluxo], curva: CurvaPre) -> float:
    """PU com cada fluxo descontado pela taxa zero da curva no seu prazo."""
    return float(sum(f.valor * curva.fator_desconto(float(f.du)) for f in fluxos))


def _resolver(f: Callable[[float], float], alvo: float, lo: float = -0.5, hi: float = 2.0) -> float:
    """Raiz de f(x) = alvo por bisseção; f precisa ser decrescente em x."""
    f_lo, f_hi = f(lo) - alvo, f(hi) - alvo
    if f_lo < 0 or f_hi > 0:
        raise ValueError("sem solução no intervalo de taxas")
    for _ in range(200):
        meio = (lo + hi) / 2
        if f(meio) - alvo > 0:
            lo = meio
        else:
            hi = meio
        if hi - lo < 1e-13:
            break
    return (lo + hi) / 2


def taxa_por_pu(fluxos: Sequence[Fluxo], pu: float) -> float:
    """Yield (taxa única) que reprecifica o PU."""
    if not fluxos or pu <= 0:
        raise ValueError("fluxos vazios ou PU não positivo")
    return _resolver(lambda t: pu_por_taxa(fluxos, t), pu)


@dataclass(frozen=True)
class Ltn:
    vencimento: dt.date
    du: int
    taxa: float


@dataclass(frozen=True)
class Ntnf:
    vencimento: dt.date
    fluxos: tuple[Fluxo, ...]
    pu: float

    @property
    def du(self) -> int:
        return self.fluxos[-1].du


@dataclass(frozen=True)
class ResultadoBootstrap:
    curva: CurvaPre
    #: DU do vértice → "CDI", "LTN" ou "NTN-F": de onde saiu cada vértice.
    origem: dict[int, str]
    #: NTN-F que não entraram (vencem dentro da curva das LTN): erro de preço em R$.
    erros_ntnf: dict[dt.date, float]


def bootstrap(
    ltns: Sequence[Ltn], ntnfs: Sequence[Ntnf], *, ancora_cdi: float | None = None
) -> ResultadoBootstrap:
    """Curva pré a partir das LTN e das NTN-F que vencem depois da última LTN.

    Com ``ancora_cdi``, o CDI entra como vértice de 1 DU: sem ele, antes da primeira LTN
    (em geral a 3 ou 4 meses) a curva repetiria a taxa dessa LTN.
    """
    if not ltns:
        raise ValueError("é preciso ao menos uma LTN")
    du = [float(x.du) for x in ltns]
    taxas = [x.taxa for x in ltns]
    origem = {x.du: "LTN" for x in ltns}
    if ancora_cdi is not None and min(du) > 1:
        du.insert(0, 1.0)
        taxas.insert(0, ancora_cdi)
        origem[1] = "CDI"
    curva = CurvaPre(du, taxas)
    erros: dict[dt.date, float] = {}
    for n in sorted(ntnfs, key=lambda x: x.du):
        if n.du <= curva.du[-1]:
            erros[n.vencimento] = pu_por_curva(n.fluxos, curva) - n.pu
            continue
        base_du, base_tx = list(curva.du), list(curva.taxas)

        def pu_com_vertice(
            z: float, base_du: list[float] = base_du, base_tx: list[float] = base_tx, n: Ntnf = n
        ) -> float:
            return pu_por_curva(n.fluxos, CurvaPre([*base_du, float(n.du)], [*base_tx, z]))

        z = _resolver(pu_com_vertice, n.pu)
        curva = CurvaPre([*base_du, float(n.du)], [*base_tx, z])
        origem[n.du] = "NTN-F"
    return ResultadoBootstrap(curva, origem, erros)
