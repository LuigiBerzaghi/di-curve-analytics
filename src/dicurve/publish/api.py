"""Monta os JSON do contrato de dados (``data/api/``) a partir dos dados salvos e do motor.

As funções ``*_json`` são puras: recebem tabelas e curvas e devolvem dicionários prontos
para serializar. ``montar`` lê o armazenamento local; ``escrever`` grava os arquivos.

Uso:
    dicurve-publicar --data 2026-11-24 --destino data/api

A curva vem de dados abertos (LTN e NTN-F negociadas no Selic e CDI, BCB, licença ODbL).
Só gera os arquivos se as verificações do dia forem aprovadas.
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
from dicurve.engine.curva import VERTICES_PADRAO, CurvaPre
from dicurve.engine.forwards import forwards_entre_vertices, metricas_forma
from dicurve.engine.risco import Posicao, dv01_por_posicao, key_rate_dv01, metricas_carteira
from dicurve.engine.titulos import ResultadoBootstrap, taxa_por_pu
from dicurve.ingest import bcb_titulos
from dicurve.ingest.atualizar import RAIZ_PADRAO, caminho_titulos, ler_cdi
from dicurve.qa.titulos import verificar_titulos
from dicurve.qa.verificacoes import Resultado, aprovado
from dicurve.simulado import balanco, carteira

VERSAO_CONTRATO = 1
FONTE = bcb_titulos.FONTE
CHOQUES_PARALELOS = (-200, -100, -50, 50, 100, 200)
PREGOES_SUPERFICIE = 120
DIAS_MANTIDOS = 20

Json = dict[str, Any]


def _r(x: float, casas: int) -> float:
    return round(float(x), casas)


def _cabecalho(data_base: dt.date, *, simulado: bool = False) -> Json:
    cab: Json = {"versao": VERSAO_CONTRATO, "data_base": data_base.isoformat()}
    cab["fonte"] = "Simulado sobre a curva de " + FONTE if simulado else FONTE
    return cab


def titulos_json(
    df: pd.DataFrame,
    data: dt.date,
    cal: CalendarioDU,
    resultado: ResultadoBootstrap,
    anterior: dt.date | None = None,
) -> Json:
    """Títulos negociados no dia (taxa da LTN, yield da NTN-F) e os vértices da curva."""
    ltns, ntnfs = bcb_titulos.titulos_do_dia(df, data, cal)
    taxas_ant: dict[tuple[str, dt.date], float] = {}
    if anterior is not None:
        l0, n0 = bcb_titulos.titulos_do_dia(df, anterior, cal)
        taxas_ant |= {("LTN", x.vencimento): x.taxa for x in l0}
        taxas_ant |= {("NTN-F", n.vencimento): taxa_por_pu(n.fluxos, n.pu) for n in n0}
    dia = {
        (sg, v): (pu, op, q)
        for sg, v, pu, op, q in zip(
            *(
                df[df["data_base"] == data][c]
                for c in ("sigla", "vencimento", "pu_med", "num_oper", "quantidade")
            ),
            strict=True,
        )
    }
    titulos = []
    for sigla, venc, du, taxa in [("LTN", x.vencimento, x.du, x.taxa) for x in ltns] + [
        ("NTN-F", n.vencimento, n.du, taxa_por_pu(n.fluxos, n.pu)) for n in ntnfs
    ]:
        pu, operacoes, quantidade = dia[(sigla, venc)]
        ant = taxas_ant.get((sigla, venc))
        titulos.append(
            {
                "sigla": sigla,
                "vencimento": venc.isoformat(),
                "du": int(du),
                "taxa": _r(taxa, 6),
                "pu_medio": _r(float(pu), 6),
                "operacoes": int(operacoes),
                "quantidade": int(quantidade),
                "delta_bps": None if ant is None else _r((taxa - ant) * 1e4, 2),
            }
        )
    vertices = [
        {"du": int(du), "taxa": _r(tx, 6), "origem": resultado.origem.get(int(du), "")}
        for du, tx in zip(resultado.curva.du, resultado.curva.taxas, strict=True)
    ]
    return {**_cabecalho(data), "titulos": titulos, "vertices_curva": vertices}


def vertices_json(data: dt.date, curva: CurvaPre, anterior: CurvaPre | None = None) -> Json:
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


def forwards_json(data: dt.date, curva: CurvaPre) -> Json:
    trechos = [
        {"du_inicio": t.du_inicio, "du_fim": t.du_fim, "taxa": _r(t.taxa, 6)}
        for t in forwards_entre_vertices(curva)
    ]
    return {**_cabecalho(data), "trechos": trechos}


def risco_json(data: dt.date, curva: CurvaPre, posicoes: Sequence[Posicao]) -> Json:
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


def alm_json(data: dt.date, curva: CurvaPre, faixas: Sequence[FaixaBalanco]) -> Json:
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


def superficie_json(historico: Sequence[tuple[dt.date, CurvaPre]]) -> Json:
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
    raiz: Path = RAIZ_PADRAO,
    *,
    cal: CalendarioDU | None = None,
    pregoes_superficie: int = PREGOES_SUPERFICIE,
) -> dict[str, Json]:
    """Lê os dados abertos e devolve ``{caminho: conteúdo}``. Levanta ``DiaReprovadoError``."""
    cal = cal or CalendarioDU.anbima()
    df = bcb_titulos.de_csv(caminho_titulos(raiz))
    cdi = ler_cdi(raiz)
    todas = bcb_titulos.datas(df)
    if data not in todas:
        raise ValueError(f"sem negociações em {data:%d/%m/%Y}")
    datas = [d for d in todas if d <= data][-pregoes_superficie:]

    def curva(d: dt.date) -> ResultadoBootstrap:
        return bcb_titulos.curva_do_dia(df, d, cal, float(cdi[d]) if d in cdi.index else None)

    resultados = {d: curva(d) for d in datas}
    hoje = resultados[data]
    anterior = datas[-2] if len(datas) > 1 else None
    curva_ant = resultados[anterior].curva if anterior else None
    verificacoes = verificar_titulos(df, data, cal, hoje, curva_ant)
    if not aprovado(verificacoes):
        raise DiaReprovadoError(f"verificações reprovadas em {data:%d/%m/%Y}")

    pasta = data.isoformat()
    return {
        f"{pasta}/curve.json": titulos_json(df, data, cal, hoje, anterior),
        f"{pasta}/vertices.json": vertices_json(data, hoje.curva, curva_ant),
        f"{pasta}/forwards.json": forwards_json(data, hoje.curva),
        f"{pasta}/risk.json": risco_json(data, hoje.curva, carteira()),
        f"{pasta}/alm.json": alm_json(data, hoje.curva, balanco()),
        f"{pasta}/qa.json": qa_json(data, verificacoes),
        f"history/surface-{pregoes_superficie}d.json": superficie_json(
            [(d, r.curva) for d, r in resultados.items()]
        ),
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


def podar(destino: Path, manter: int = DIAS_MANTIDOS) -> list[Path]:
    """Apaga as pastas de dias mais antigas, mantendo as ``manter`` mais recentes."""
    pastas = (
        sorted(p for p in destino.iterdir() if p.is_dir() and p.name[:4].isdigit())
        if destino.exists()
        else []
    )
    removidas = pastas[:-manter] if manter > 0 else pastas
    for pasta in removidas:
        for arq in pasta.iterdir():
            arq.unlink()
        pasta.rmdir()
    return removidas


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gera os JSON do contrato de dados para um dia.")
    p.add_argument(
        "--data", type=dt.date.fromisoformat, help="data-base (padrão: último dia salvo)"
    )
    p.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="pasta dos dados abertos")
    p.add_argument("--destino", type=Path, default=Path("data/api"), help="pasta de saída")
    p.add_argument("--manter", type=int, default=DIAS_MANTIDOS, help="dias mantidos na pasta")
    args = p.parse_args(argv)

    arq = caminho_titulos(args.raiz)
    datas = bcb_titulos.datas(bcb_titulos.de_csv(arq)) if arq.exists() else []
    data = args.data or (datas[-1] if datas else None)
    if data is None or data not in datas:
        print("Sem dados para a data pedida.", file=sys.stderr)
        return 2
    try:
        arquivos = montar(data, args.raiz)
    except DiaReprovadoError as erro:
        print(f"Nada gerado: {erro}.", file=sys.stderr)
        return 1
    escritos = escrever(arquivos, args.destino, data)
    podar(args.destino, args.manter)
    print(f"{len(escritos)} arquivos em {args.destino} para {data:%d/%m/%Y}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
