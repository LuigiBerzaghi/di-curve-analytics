"""Motor de cálculo: funções puras, sem acesso a rede ou disco.

Módulos:
    calendario  dias úteis com feriados nacionais (padrão ANBIMA) e vencimentos do DI1
    curva       PU ↔ taxa, fator de desconto e a curva com interpolação flat-forward
    forwards    taxas a termo, spreads e métricas de forma (nível, inclinação, curvatura)
    risco       duration, convexidade, DV01, key rate DV01 e reprecificação exata
    cenarios    choques paralelos, de inclinação, macro e personalizados
    alm         gap de reprecificação, ΔEVE, ΔNII e duration gap
"""
