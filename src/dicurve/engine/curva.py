"""PU, taxa, fator de desconto e a curva DI com interpolação flat-forward.

Convenções: base 252 dias úteis, capitalização exponencial, taxas como fração
(0.1350 = 13,50% a.a.) e face do DI1 de R$ 100.000.

Flat-forward
------------
Entre dois vértices a taxa a termo é constante. Isso equivale a interpolar
linearmente o logaritmo do fator de capitalização ``ln F(du) = du/252 · ln(1 + taxa)``.

Nas pontas:
- antes do primeiro vértice, vale a taxa do primeiro vértice;
- depois do último vértice, vale a taxa do último vértice (mesma convenção do PYield).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dicurve import DIAS_UTEIS_ANO, FACE_DI1

Vetor = NDArray[np.float64]

#: Vértices padrão de mercado em dias úteis.
VERTICES_PADRAO: dict[str, int] = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1A": 252,
    "2A": 504,
    "3A": 756,
    "5A": 1260,
    "7A": 1764,
    "10A": 2520,
}


def fator_capitalizacao[Num: (float, Vetor)](taxa: Num, du: Num) -> Num:
    """(1 + taxa)^(du/252)."""
    fator: Num = (1.0 + taxa) ** (du / DIAS_UTEIS_ANO)
    return fator


def fator_desconto[Num: (float, Vetor)](taxa: Num, du: Num) -> Num:
    """1 / (1 + taxa)^(du/252): quanto vale hoje R$ 1 pago em ``du`` dias úteis."""
    return 1.0 / fator_capitalizacao(taxa, du)


def pu_de_taxa[Num: (float, Vetor)](taxa: Num, du: Num, face: float = FACE_DI1) -> Num:
    """PU = face / (1 + taxa)^(du/252)."""
    return face * fator_desconto(taxa, du)


def taxa_de_pu[Num: (float, Vetor)](pu: Num, du: Num, face: float = FACE_DI1) -> Num:
    """Taxa = (face / PU)^(252/du) − 1. Exige ``du > 0``."""
    if np.any(np.asarray(du) <= 0):
        raise ValueError("du precisa ser positivo para converter PU em taxa")
    taxa: Num = (face / pu) ** (DIAS_UTEIS_ANO / du) - 1.0
    return taxa


class CurvaPre:
    """Curva de taxas pré definida por vértices (DU, taxa), com interpolação flat-forward."""

    def __init__(self, du: ArrayLike, taxas: ArrayLike) -> None:
        du_arr = np.asarray(du, dtype=np.float64).ravel()
        tx_arr = np.asarray(taxas, dtype=np.float64).ravel()
        if du_arr.size == 0 or du_arr.size != tx_arr.size:
            raise ValueError("du e taxas precisam ter o mesmo tamanho, maior que zero")
        if np.any(du_arr <= 0):
            raise ValueError("todos os vértices precisam ter du > 0")
        if np.any(~np.isfinite(tx_arr)) or np.any(tx_arr <= -1.0):
            raise ValueError("taxas precisam ser finitas e maiores que −100%")
        ordem = np.argsort(du_arr, kind="stable")
        du_arr, tx_arr = du_arr[ordem], tx_arr[ordem]
        if np.any(np.diff(du_arr) == 0):
            raise ValueError("há vértices repetidos")
        self._du: Vetor = du_arr
        self._taxas: Vetor = tx_arr
        self._log_fator: Vetor = du_arr / DIAS_UTEIS_ANO * np.log1p(tx_arr)

    @property
    def du(self) -> Vetor:
        return self._du.copy()

    @property
    def taxas(self) -> Vetor:
        return self._taxas.copy()

    def __len__(self) -> int:
        return int(self._du.size)

    def __repr__(self) -> str:
        return f"CurvaPre({len(self)} vértices, du {self._du[0]:.0f}–{self._du[-1]:.0f})"

    def _log_fator_em(self, du: Vetor) -> Vetor:
        ultimo = self._du[-1]
        interno = np.interp(du, np.r_[0.0, self._du], np.r_[0.0, self._log_fator])
        longo = du / DIAS_UTEIS_ANO * np.log1p(self._taxas[-1])
        return np.where(du > ultimo, longo, interno)

    def taxa[Num: (float, Vetor)](self, du: Num) -> Num:
        """Taxa zero interpolada (flat-forward) para ``du`` dias úteis."""
        x = np.asarray(du, dtype=np.float64)
        seguro = np.where(x > 0, x, 1.0)
        tx = np.expm1(self._log_fator_em(seguro) * DIAS_UTEIS_ANO / seguro)
        tx = np.where(x > 0, tx, self._taxas[0])
        return _como_entrada(tx, du)

    def fator_capitalizacao[Num: (float, Vetor)](self, du: Num) -> Num:
        x = np.asarray(du, dtype=np.float64)
        return _como_entrada(np.exp(self._log_fator_em(x)), du)

    def fator_desconto[Num: (float, Vetor)](self, du: Num) -> Num:
        x = np.asarray(du, dtype=np.float64)
        return _como_entrada(np.exp(-self._log_fator_em(x)), du)

    def pu[Num: (float, Vetor)](self, du: Num, face: float = FACE_DI1) -> Num:
        x = np.asarray(du, dtype=np.float64)
        return _como_entrada(face * np.exp(-self._log_fator_em(x)), du)

    def forward(self, du1: float, du2: float) -> float:
        """Taxa a termo entre ``du1`` e ``du2`` (``du2 > du1``)."""
        if du2 <= du1:
            raise ValueError("du2 precisa ser maior que du1")
        lf = self._log_fator_em(np.array([du1, du2], dtype=np.float64))
        return float(np.expm1((lf[1] - lf[0]) * DIAS_UTEIS_ANO / (du2 - du1)))

    def vertices_padrao(self) -> dict[str, float]:
        """Taxas nos vértices padrão (1M, 3M, …, 10A)."""
        prazos = np.array(list(VERTICES_PADRAO.values()), dtype=np.float64)
        taxas = self.taxa(prazos)
        return dict(zip(VERTICES_PADRAO, (float(t) for t in taxas), strict=True))

    def com_taxas(self, taxas: ArrayLike) -> CurvaPre:
        """Nova curva com os mesmos vértices e outras taxas."""
        return CurvaPre(self._du, taxas)


def _como_entrada[Num: (float, Vetor)](resultado: Vetor, entrada: Num) -> Num:
    """Devolve escalar se a entrada era escalar; senão, o vetor."""
    if np.ndim(entrada) == 0:
        return float(resultado)  # type: ignore[return-value]
    return resultado  # type: ignore[return-value]
