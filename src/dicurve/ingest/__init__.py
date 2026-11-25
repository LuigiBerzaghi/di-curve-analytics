"""Coletores de dados públicos. Único subpacote que acessa a rede.

Módulos:
    b3_di1         ajustes diários do DI1 (B3, via PYield)
    bcb            séries do SGS: CDI anualizado (4389) e Selic meta (432)
    armazenamento  Parquet local em data/raw/, fora do Git
    atualizar      coleta de um dia + verificações (comando dicurve-atualizar)
"""
