"""Verificações diárias da curva pré montada com LTN e NTN-F (dados do BCB).

Mesma lógica das verificações do DI1: "erro" bloqueia a publicação do dia, "alerta" só
fica registrado. Os limites foram calibrados nos pregões de dez/2024 a nov/2026
(docs/02-metodologia.md).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.curva import CurvaPre
from dicurve.engine.forwards import forwards_entre_vertices
from dicurve.engine.titulos import ResultadoBootstrap, pu_ltn, taxa_por_pu
from dicurve.ingest.bcb_titulos import titulos_do_dia
from dicurve.qa.verificacoes import Resultado, _lista

VERTICES_VARIACAO = ("1A", "2A", "3A", "5A", "7A", "10A")


def verificar_titulos(
    df: pd.DataFrame,
    data: dt.date,
    cal: CalendarioDU,
    resultado: ResultadoBootstrap,
    anterior: CurvaPre | None = None,
    *,
    min_ltn: int = 4,
    prazo_min_du: int = 1260,
    banda: tuple[float, float] = (0.02, 0.30),
    tolerancia_pu: float = 0.01,
    limite_ntnf_bps: float = 25.0,
    limite_variacao_bps: float = 50.0,
) -> list[Resultado]:
    ltns, ntnfs = titulos_do_dia(df, data, cal)
    curva = resultado.curva
    out: list[Resultado] = []

    # 1. títulos suficientes
    prazo = int(curva.du[-1])
    ok = len(ltns) >= min_ltn and prazo >= prazo_min_du
    out.append(
        Resultado(
            "titulos_suficientes",
            f"Ao menos {min_ltn} LTN e curva até {prazo_min_du} DU",
            ok,
            f"{len(ltns)} LTN, {len(ntnfs)} NTN-F, curva até {prazo} DU",
        )
    )

    # 2. banda de taxa (LTN e yield das NTN-F)
    taxas = {f"LTN {x.vencimento:%m/%Y}": x.taxa for x in ltns}
    taxas |= {f"NTN-F {n.vencimento:%m/%Y}": taxa_por_pu(n.fluxos, n.pu) for n in ntnfs}
    fora = [k for k, t in taxas.items() if not banda[0] <= t <= banda[1]]
    out.append(
        Resultado(
            "banda_taxa",
            f"Taxas entre {banda[0]:.0%} e {banda[1]:.0%} a.a.",
            not fora,
            f"{min(taxas.values()):.3%} a {max(taxas.values()):.3%}" if not fora else _lista(fora),
        )
    )

    # 3. PU das LTN recalculado: PU mínimo do BCB contra a taxa máxima (mesma operação)
    dia = df[(df["data_base"] == data) & (df["sigla"] == "LTN")].dropna(
        subset=["taxa_max", "pu_min"]
    )
    difs = {
        f"LTN {v:%m/%Y}": abs(pu_ltn(float(t), cal.contar(data, v)) - float(p))
        for v, t, p in zip(dia["vencimento"], dia["taxa_max"], dia["pu_min"], strict=True)
    }
    ruins = [k for k, d in difs.items() if d > tolerancia_pu]
    out.append(
        Resultado(
            "pu_recalculado",
            f"PU das LTN a até R$ {tolerancia_pu:.2f} do divulgado pelo BCB",
            not ruins,
            (
                f"maior diferença R$ {max(difs.values()):.4f} em {len(difs)} LTN"
                if difs
                else "sem taxa divulgada"
            )
            if not ruins
            else _lista(ruins),
        )
    )

    # 4. sem arbitragem
    negativas = [
        f"{t.du_inicio}–{t.du_fim} DU" for t in forwards_entre_vertices(curva) if t.taxa <= 0
    ]
    out.append(
        Resultado(
            "sem_arbitragem",
            "Todas as forwards entre vértices positivas",
            not negativas,
            "todas positivas" if not negativas else _lista(negativas),
        )
    )

    # 5. NTN-F dentro da faixa das LTN: yield de mercado × yield pela curva das LTN
    desvios = {}
    for n in ntnfs:
        if n.vencimento in resultado.erros_ntnf:
            pu_curva = n.pu + resultado.erros_ntnf[n.vencimento]
            desvios[f"NTN-F {n.vencimento:%m/%Y}"] = (
                taxa_por_pu(n.fluxos, n.pu) - taxa_por_pu(n.fluxos, pu_curva)
            ) * 1e4
    grandes = [f"{k} {d:+.1f}" for k, d in desvios.items() if abs(d) > limite_ntnf_bps]
    out.append(
        Resultado(
            "ntnf_coerente",
            f"NTN-F a até {limite_ntnf_bps:.0f} bps da curva das LTN",
            not grandes,
            (
                f"maior desvio {max(abs(d) for d in desvios.values()):.1f} bps"
                if desvios
                else "nenhuma NTN-F na faixa das LTN"
            )
            if not grandes
            else _lista(grandes),
            gravidade="alerta",
        )
    )

    # 6. variação diária dos vértices
    if anterior is None:
        out.append(
            Resultado(
                "variacao_diaria",
                "Variação diária dos vértices",
                True,
                "sem dia anterior",
                "alerta",
            )
        )
    else:
        v, va = curva.vertices_padrao(), anterior.vertices_padrao()
        delta = {k: (v[k] - va[k]) * 1e4 for k in VERTICES_VARIACAO}
        acima = [f"{k} {d:+.1f}" for k, d in delta.items() if abs(d) > limite_variacao_bps]
        out.append(
            Resultado(
                "variacao_diaria",
                f"Vértices de 1A a 10A variando até {limite_variacao_bps:.0f} bps",
                not acima,
                f"maior variação {max(abs(d) for d in delta.values()):.1f} bps"
                if not acima
                else _lista(acima),
                gravidade="alerta",
            )
        )
    return out
