"""Monta os JSON do contrato de dados (``data/api/``) a partir dos dados salvos e do motor.

As funções ``*_json`` são puras: recebem tabelas e curvas e devolvem dicionários prontos
para serializar. ``montar`` lê o armazenamento local; ``escrever`` grava os arquivos.

Uso:
    dicurve-publicar --data 2026-11-23 --destino data/api

Só gera os arquivos se as verificações do dia forem aprovadas. Enquanto a decisão 5 do
plano (termos da B3) estiver pendente, os arquivos ficam só na máquina ou no runner do
job: nada calculado com dados da B3 é versionado.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from dicurve.engine.alm import FaixaBalanco, delta_eve, delta_nii, duration_gap, gaps
from dicurve.engine.calendario import CalendarioDU
from dicurve.engine.cenarios import CENARIOS_MACRO, REGIMES_INCLINACAO, paralelo
from dicurve.engine.cenarios import delta_pv_total as _delta_pv_total
from dicurve.engine.curva import VERTICES_PADRAO, CurvaDI, pu_de_taxa
from dicurve.engine.forwards import forwards_entre_vertices, metricas_forma
from dicurve.engine.risco import Posicao, dv01_por_posicao, key_rate_dv01, metricas_carteira
from dicurve.ingest import armazenamento, b3_di1
from dicurve.qa.verificacoes import Resultado, aprovado, verificar_di1
from dicurve.simulado import balanco, carteira

VERSAO_CONTRATO = 1
FONTE_B3 = "B3, ajustes do DI1; cálculo próprio"
CHOQUES_PARALELOS = (-200, -100, -50, 50, 100, 200)
PREGOES_SUPERFICIE = 120

Json = dict[str, Any]


def _r(x: float, casas: int) -> float:
    return round(float(x), casas)


def _cabecalho(data_base: dt.date, *, simulado: bool = False) -> Json:
    cab: Json = {"versao": VERSAO_CONTRATO, "data_base": data_base.isoformat()}
    cab["fonte"] = "Simulado sobre a curva " + FONTE_B3 if simulado else FONTE_B3
    return cab


def curva_json(hoje: pd.DataFrame, anterior: pd.DataFrame | None = None) -> Json:
    """Contratos do dia: código, vencimento, DU, taxa, PU do motor e variação em bps."""
    data = hoje["data_base"].iloc[0]
    ant = (
        {}
        if anterior is None
        else dict(zip(anterior["codigo"], anterior["taxa_ajuste"], strict=True))
    )
    contratos = []
    for c, venc, du, tx in zip(
        hoje["codigo"], hoje["vencimento"], hoje["du_b3"], hoje["taxa_ajuste"], strict=True
    ):
        delta = None if c not in ant else _r((tx - ant[c]) * 1e4, 2)
        contratos.append(
            {
                "codigo": c,
                "vencimento": venc.isoformat(),
                "du": int(du),
                "taxa": _r(tx, 6),
                "pu": _r(pu_de_taxa(float(tx), float(du)), 2),
                "delta_bps": delta,
            }
        )
    return {**_cabecalho(data), "contratos": contratos}


def vertices_json(data: dt.date, curva: CurvaDI, anterior: CurvaDI | None = None) -> Json:
    """Vértices padrão interpolados (flat-forward) e métricas de forma."""
    v = curva.vertices_padrao()
    va = None if anterior is None else anterior.vertices_padrao()
    forma = metricas_forma(curva)
    return {
        **_cabecalho(data),
        "vertices": [
            {
                "prazo": nome,
                "du": VERTICES_PADRAO[nome],
                "taxa": _r(v[nome], 6),
                "delta_bps": None if va is None else _r((v[nome] - va[nome]) * 1e4, 2),
            }
            for nome in VERTICES_PADRAO
        ],
        "forma": {
            "nivel": _r(forma.nivel, 6),
            "inclinacao_bps": _r(forma.inclinacao_bps, 2),
            "curvatura_bps": _r(forma.curvatura_bps, 2),
        },
    }


def forwards_json(data: dt.date, curva: CurvaDI) -> Json:
    trechos = [
        {"du_inicio": t.du_inicio, "du_fim": t.du_fim, "taxa": _r(t.taxa, 6)}
        for t in forwards_entre_vertices(curva)
    ]
    return {**_cabecalho(data), "trechos": trechos}


def risco_json(data: dt.date, curva: CurvaDI, posicoes: Sequence[Posicao]) -> Json:
    """Risco da carteira simulada: DV01, duration, convexidade, key rate e cenários."""
    m = metricas_carteira(posicoes, curva)
    dv01_pos = dv01_por_posicao(posicoes, curva)
    cenarios: dict[str, float] = {
        f"{b:+d} bps": _r(_delta_pv_total(posicoes, curva, paralelo(b)), 0)
        for b in CHOQUES_PARALELOS
    }
    for nome, choque in {**REGIMES_INCLINACAO, **CENARIOS_MACRO}.items():
        cenarios[nome] = _r(_delta_pv_total(posicoes, curva, choque), 0)
    return {
        **_cabecalho(data, simulado=True),
        "metricas": {
            "pv_liquido": _r(m.pv_liquido, 0),
            "pv_bruto": _r(m.pv_bruto, 0),
            "dv01": _r(m.dv01, 2),
            "duration_modificada": _r(m.duration_modificada, 4),
            "convexidade": _r(m.convexidade, 4),
        },
        "posicoes": [
            {
                "nome": p.nome,
                "du": p.du,
                "pv": _r(p.pv, 0),
                "taxa": _r(curva.taxa(float(p.du)), 6),
                "dv01": _r(dv01_pos[p.nome], 2),
            }
            for p in posicoes
        ],
        "key_rate_dv01": {k: _r(v, 2) for k, v in key_rate_dv01(posicoes, curva).items()},
        "cenarios_delta_pv": cenarios,
    }


def alm_json(data: dt.date, curva: CurvaDI, faixas: Sequence[FaixaBalanco]) -> Json:
    """Gap por faixa, duration gap e ΔEVE/ΔNII em choques paralelos (balanço simulado)."""
    return {
        **_cabecalho(data, simulado=True),
        "faixas": [
            {
                "nome": f.nome,
                "du_medio": f.du_medio,
                "ativos": _r(f.ativos, 0),
                "passivos": _r(f.passivos, 0),
                "gap": _r(g, 0),
            }
            for f, g in zip(faixas, gaps(faixas), strict=True)
        ],
        "duration_gap": _r(duration_gap(faixas, curva), 4),
        "choques": [
            {
                "bps": b,
                "delta_eve": _r(delta_eve(faixas, curva, paralelo(b)), 0),
                "delta_nii_12m": _r(delta_nii(faixas, paralelo(b)), 0),
            }
            for b in CHOQUES_PARALELOS
        ],
    }


def qa_json(data: dt.date, resultados: Sequence[Resultado]) -> Json:
    return {
        **_cabecalho(data),
        "aprovado": aprovado(resultados),
        "verificacoes": [
            {
                "nome": r.nome,
                "regra": r.regra,
                "ok": r.ok,
                "gravidade": r.gravidade,
                "detalhe": r.detalhe,
            }
            for r in resultados
        ],
    }


def superficie_json(historico: Sequence[tuple[dt.date, CurvaDI]]) -> Json:
    """Matriz data × prazo com as taxas dos vértices padrão, em ordem cronológica."""
    if not historico:
        raise ValueError("histórico vazio")
    historico = sorted(historico, key=lambda par: par[0])
    nomes = list(VERTICES_PADRAO)
    return {
        **_cabecalho(historico[-1][0]),
        "prazos": nomes,
        "du": [VERTICES_PADRAO[n] for n in nomes],
        "datas": [d.isoformat() for d, _ in historico],
        "taxas": [[_r(c.vertices_padrao()[n], 6) for n in nomes] for _, c in historico],
    }


class DiaReprovadoError(RuntimeError):
    """As verificações do dia falharam: nada é gerado."""


def montar(
    data: dt.date,
    raiz: Path = armazenamento.RAIZ_PADRAO,
    *,
    cal: CalendarioDU | None = None,
    pregoes_superficie: int = PREGOES_SUPERFICIE,
) -> dict[str, Json]:
    """Lê os dados salvos e devolve ``{caminho: conteúdo}``. Levanta ``DiaReprovadoError``."""
    cal = cal or CalendarioDU.anbima()
    hoje = armazenamento.ler("b3_di1", data, raiz)
    datas = [d for d in armazenamento.datas_salvas("b3_di1", raiz) if d < data]
    anterior = armazenamento.ler("b3_di1", datas[-1], raiz) if datas else None
    resultados = verificar_di1(hoje, cal, anterior)
    if not aprovado(resultados):
        raise DiaReprovadoError(f"verificações reprovadas em {data:%d/%m/%Y}")

    curva = b3_di1.curva_de_ajustes(hoje)
    curva_ant = None if anterior is None else b3_di1.curva_de_ajustes(anterior)
    historico = [
        (d, b3_di1.curva_de_ajustes(armazenamento.ler("b3_di1", d, raiz)))
        for d in datas[-(pregoes_superficie - 1) :]
    ]
    historico.append((data, curva))

    pasta = data.isoformat()
    return {
        f"{pasta}/curve.json": curva_json(hoje, anterior),
        f"{pasta}/vertices.json": vertices_json(data, curva, curva_ant),
        f"{pasta}/forwards.json": forwards_json(data, curva),
        f"{pasta}/risk.json": risco_json(data, curva, carteira()),
        f"{pasta}/alm.json": alm_json(data, curva, balanco()),
        f"{pasta}/qa.json": qa_json(data, resultados),
        f"history/surface-{pregoes_superficie}d.json": superficie_json(historico),
    }


def escrever(arquivos: Mapping[str, Json], destino: Path, data: dt.date) -> list[Path]:
    """Grava os JSON e atualiza ``latest.json`` por último (o site só vê dias completos)."""
    escritos = []
    for rel, conteudo in arquivos.items():
        caminho = destino / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        escritos.append(caminho)
    latest = destino / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "versao": VERSAO_CONTRATO,
                "data_base": data.isoformat(),
                "arquivos": sorted(arquivos),
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    escritos.append(latest)
    return escritos


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gera os JSON do contrato de dados para um pregão.")
    p.add_argument(
        "--data", type=dt.date.fromisoformat, help="data-base (padrão: último pregão salvo)"
    )
    p.add_argument(
        "--raiz", type=Path, default=armazenamento.RAIZ_PADRAO, help="pasta dos dados brutos"
    )
    p.add_argument("--destino", type=Path, default=Path("data/api"), help="pasta de saída")
    args = p.parse_args(argv)

    salvas = armazenamento.datas_salvas("b3_di1", args.raiz)
    data = args.data or (salvas[-1] if salvas else None)
    if data is None or data not in salvas:
        print("Sem dados salvos para a data pedida.", file=sys.stderr)
        return 2
    try:
        arquivos = montar(data, args.raiz)
    except DiaReprovadoError as erro:
        print(f"Nada gerado: {erro}.", file=sys.stderr)
        return 1
    escritos = escrever(arquivos, args.destino, data)
    print(f"{len(escritos)} arquivos em {args.destino} para {data:%d/%m/%Y}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
