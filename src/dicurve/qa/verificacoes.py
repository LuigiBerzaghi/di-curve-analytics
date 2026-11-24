"""Verificações de qualidade dos ajustes do DI1, rodadas a cada coleta.

Cada verificação devolve um ``Resultado``. Falha com gravidade ``erro`` bloqueia a
publicação; ``alerta`` só avisa (por exemplo, uma variação diária grande pode ser real).
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from dicurve.engine.calendario import CalendarioDU, vencimento_di1
from dicurve.engine.curva import pu_de_taxa
from dicurve.engine.forwards import taxa_forward

Gravidade = Literal["erro", "alerta"]


@dataclass(frozen=True)
class Resultado:
    nome: str
    regra: str
    ok: bool
    detalhe: str
    gravidade: Gravidade = "erro"


def _lista(itens: Sequence[str], maximo: int = 5) -> str:
    extra = f" e mais {len(itens) - maximo}" if len(itens) > maximo else ""
    return ", ".join(itens[:maximo]) + extra


def verificar_di1(
    df: pd.DataFrame,
    calendario: CalendarioDU,
    anterior: pd.DataFrame | None = None,
    *,
    tolerancia_pu: float = 0.01,
    banda: tuple[float, float] = (0.02, 0.30),
    limite_variacao_bps: float = 50.0,
) -> list[Resultado]:
    """Roda as seis verificações da metodologia sobre os ajustes de uma data-base."""
    if df.empty:
        return [Resultado("dados", "Há ajustes para a data", False, "nenhum contrato recebido")]
    datas = df["data_base"].unique()
    if len(datas) != 1:
        raise ValueError("verifique uma data-base por vez")
    data_base = datas[0]
    out: list[Resultado] = []

    # 1. vértices completos
    sem = df[df["taxa_ajuste"].isna() | df["pu_ajuste"].isna()]["codigo"].tolist()
    out.append(
        Resultado(
            "vertices_completos",
            "Todos os vencimentos com taxa e PU de ajuste",
            not sem,
            f"{len(df)} contratos" if not sem else f"sem ajuste: {_lista(sem)}",
        )
    )
    v = df.dropna(subset=["taxa_ajuste", "pu_ajuste", "du_b3"]).copy()

    # 2. banda de taxa
    lo, hi = banda
    fora = v[(v["taxa_ajuste"] < lo) | (v["taxa_ajuste"] > hi)]["codigo"].tolist()
    out.append(
        Resultado(
            "banda_taxa",
            f"Taxas entre {lo:.0%} e {hi:.0%} a.a.",
            not fora,
            f"{v['taxa_ajuste'].min():.3%} a {v['taxa_ajuste'].max():.3%}"
            if not fora
            else f"fora da banda: {_lista(fora)}",
        )
    )

    # 3. variação diária
    if anterior is not None and not anterior.empty:
        m = v.merge(anterior[["codigo", "taxa_ajuste"]], on="codigo", suffixes=("", "_ant"))
        m["delta_bps"] = (m["taxa_ajuste"] - m["taxa_ajuste_ant"]) * 1e4
        grandes = m[m["delta_bps"].abs() > limite_variacao_bps]
        maior = m["delta_bps"].abs().max() if not m.empty else 0.0
        out.append(
            Resultado(
                "variacao_diaria",
                f"Variação diária até {limite_variacao_bps:.0f} bps",
                grandes.empty,
                f"maior variação {maior:.1f} bps"
                if grandes.empty
                else "acima do limite: "
                + _lista(
                    [
                        f"{c} {d:+.1f}"
                        for c, d in zip(grandes["codigo"], grandes["delta_bps"], strict=True)
                    ]
                ),
                gravidade="alerta",
            )
        )

    # 4. dias úteis e vencimentos
    erros_du = []
    for _, r in v.iterrows():
        du = calendario.contar(data_base, r["vencimento"])
        venc = vencimento_di1(r["codigo"], calendario)
        if du != int(r["du_b3"]) or venc != r["vencimento"]:
            erros_du.append(f"{r['codigo']} (DU {du} × {int(r['du_b3'])})")
    out.append(
        Resultado(
            "dias_uteis",
            "DU e vencimento do calendário iguais aos da B3",
            not erros_du,
            f"{len(v)} de {len(v)} iguais" if not erros_du else _lista(erros_du),
        )
    )

    # 5. PU recalculado
    pu_motor = [
        pu_de_taxa(float(t), float(d)) for t, d in zip(v["taxa_ajuste"], v["du_b3"], strict=True)
    ]
    v["dif_pu"] = (pd.Series(pu_motor, index=v.index) - v["pu_ajuste"]).abs()
    ruins = v[v["dif_pu"] > tolerancia_pu]
    out.append(
        Resultado(
            "pu_recalculado",
            f"PU recalculado a até R$ {tolerancia_pu:.2f} do divulgado",
            ruins.empty,
            f"maior diferença R$ {v['dif_pu'].max():.4f}"
            if ruins.empty
            else _lista(
                [f"{c} R$ {d:.4f}" for c, d in zip(ruins["codigo"], ruins["dif_pu"], strict=True)]
            ),
        )
    )

    # 6. sem arbitragem: forwards positivas
    v = v.sort_values("du_b3")
    negativas: list[str] = []
    pares = list(
        zip(v["codigo"], v["du_b3"].astype(float), v["taxa_ajuste"].astype(float), strict=True)
    )
    for (_, du1, tx1), (c, du2, tx2) in itertools.pairwise(pares):
        if du2 > du1 and taxa_forward(du1, tx1, du2, tx2) <= 0:
            negativas.append(str(c))
    out.append(
        Resultado(
            "sem_arbitragem",
            "Todas as forwards entre vencimentos positivas",
            not negativas,
            "todas positivas" if not negativas else f"forward negativa em: {_lista(negativas)}",
        )
    )
    return out


def aprovado(resultados: Sequence[Resultado]) -> bool:
    """Aprovado se nenhuma verificação com gravidade ``erro`` falhou."""
    return all(r.ok for r in resultados if r.gravidade == "erro")


def relatorio(resultados: Sequence[Resultado], titulo: str = "Verificações") -> str:
    linhas = [titulo]
    for r in resultados:
        marca = "OK    " if r.ok else ("ERRO  " if r.gravidade == "erro" else "ALERTA")
        linhas.append(f"  {marca} {r.regra}: {r.detalhe}")
    linhas.append("  => " + ("APROVADO" if aprovado(resultados) else "REPROVADO"))
    return "\n".join(linhas)
