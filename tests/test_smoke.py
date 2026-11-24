"""Testes de fumaça da Fase 0: o pacote instala, importa e expõe as convenções básicas."""

import importlib

import dicurve


def test_versao_definida() -> None:
    assert dicurve.__version__ == "0.0.1"


def test_convencoes_de_mercado() -> None:
    assert dicurve.DIAS_UTEIS_ANO == 252
    assert dicurve.FACE_DI1 == 100_000.0


def test_subpacotes_importam() -> None:
    for nome in ("engine", "ingest", "qa", "publish"):
        assert importlib.import_module(f"dicurve.{nome}") is not None
