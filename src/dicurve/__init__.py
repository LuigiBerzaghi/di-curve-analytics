"""DI Curve Analytics: curva DI, risco de taxa, cenários e ALM.

Subpacotes:
    engine   motor de cálculo (calendário, curva, forwards, risco, cenários, ALM)
    ingest   coletores de dados públicos (B3, BCB, ANBIMA)
    qa       verificações de qualidade dos dados
    publish  geração dos arquivos JSON lidos pelo site
"""

__version__ = "0.0.1"

#: Base de dias úteis por ano usada em todas as contas.
DIAS_UTEIS_ANO = 252

#: Valor de face do contrato DI1, em R$.
FACE_DI1 = 100_000.0
