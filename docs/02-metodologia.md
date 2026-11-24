# Metodologia

## Convenções

| Item | Convenção |
|---|---|
| Base de dias | 252 dias úteis |
| Capitalização | Exponencial (composta) |
| Unidade de taxa | % a.a. |
| Valor de face DI1 | R$ 100.000 |
| Interpolação | Flat-forward entre vencimentos |
| Choques | bps somados à taxa a.a. |
| Data-base | Fechamento D0 |
| Calendário | Feriados nacionais (lista da ANBIMA) |

## Pipeline

1. **Coleta:** ajustes do DI1 na B3, CDI e Selic no BCB, feriados na ANBIMA → taxas e PUs brutos
2. **Calendário:** dias úteis entre a data-base e cada vencimento → DU por contrato
3. **Vértices:** conversão PU ↔ taxa e validação contra o PU divulgado → curva nos vencimentos
4. **Interpolação:** flat-forward base 252 → curva para qualquer prazo
5. **Métricas:** forwards, spreads, DV01, key rates, duration, convexidade
6. **Cenários e ALM:** choques na curva, reprecificação exata, EVE e NII

## Fórmulas e racional

### PU e taxa
```
PU = 100.000 / (1 + i)^(DU/252)
i  = (100.000 / PU)^(252/DU) − 1
```
O DI1 é negociado em taxa, mas liquida em PU. Como o PU é uma curva convexa na taxa, a mesma variação em bps mexe mais no PU quando a taxa cai do que quando sobe.

### Fator de desconto
```
FD = 1 / (1 + i)^(DU/252)
```
Quanto vale hoje R$ 1 recebido no vencimento.

### Interpolação flat-forward
```
(1+i)^(DU/252) = (1+i₁)^(DU₁/252) × [(1+i₂)^(DU₂/252) / (1+i₁)^(DU₁/252)]^((DU−DU₁)/(DU₂−DU₁))
```
Entre dois vencimentos, a forward fica constante: é a hipótese mais neutra e é o padrão do mercado brasileiro. A interpolação linear na taxa parece parecida no gráfico da taxa, mas cria forwards inclinadas e saltos nos vértices (a tela *Dados e metodologia* mostra os dois gráficos lado a lado).

### Forward entre vencimentos
```
f₁,₂ = [(1+i₂)^t₂ / (1+i₁)^t₁]^(1/(t₂−t₁)) − 1      com t = DU/252
```
A taxa que deixa indiferente aplicar direto até t₂ ou aplicar até t₁ e renovar.

### Métricas de forma da curva
- **Nível:** taxa do vértice de 2 anos
- **Inclinação:** taxa 10A − taxa 2A, em bps
- **Curvatura:** taxa 1A − 2 × taxa 2A + taxa 3A, em bps

### DV01, duration e convexidade (título zero cupom)
```
Dmac = DU/252
Dmod = Dmac / (1+i)
DV01 = PV × Dmod × 0,0001
C    = t(t+1) / (1+i)²
ΔPV ≈ −Dmod·PV·Δi + ½·C·PV·Δi²
```
A duration é a inclinação da curva PU × taxa; a convexidade é a curvatura. **Nas telas de cenário a aproximação não é usada**: cada posição é reprecificada exatamente na taxa chocada:
```
ΔPV = PV × [(1+i)^t / (1+i+s)^t − 1]
```

### Key rate DV01
O choque é aplicado em um único vértice por vez (1A, 2A, 3A, 5A, 7A, 10A+), e cada contrato é alocado ao vértice mais próximo.

### Cenários
- **Paralelos:** −200 a +200 bps em toda a curva
- **Inclinação:** pivô linear entre 3M e 10A (bull/bear steepening, bull/bear flattening)
- **Macro:** vetores de choque por vértice (Copom hawkish, estresse fiscal, desinflação, risk-off global)
- **Personalizado:** choque definido pelo usuário em 6 vértices, interpolado linearmente entre eles

### ALM
```
ΔEVE   = Σ ΔPV(ativos) − Σ ΔPV(passivos)
ΔNII₁₂ = Σ gap(faixas ≤ 12M) × Δi × prazo restante no ano
Duration gap = D_ativo − D_passivo × (Passivo / Ativo)
```
O balanço é agregado em 5 faixas (≤3M, 3–12M, 1–2A, 2–5A, >5A), cada uma tratada no ponto médio.

## Verificações de qualidade (a cada fechamento)

| Verificação | Regra |
|---|---|
| Vértices completos | Todos os vencimentos com ajuste |
| Banda de taxa | Entre 2% e 30% a.a. |
| Variação diária | Sinalizar acima de 25 bps |
| Dias úteis | Calendário de feriados aplicado |
| PU recalculado | Diferença de até R$ 0,01 do divulgado |
| Sem arbitragem | Todas as forwards positivas |

## Premissas e limitações

1. Nesta versão, cotações, carteira e balanço são ilustrativos.
2. Choques são instantâneos: sem rebalanceamento, carrego ou passagem de tempo.
3. O balanço de ALM é agregado por faixa e cada faixa é tratada no ponto médio.
4. Sem risco de base, spread de crédito ou opcionalidade (pré-pagamento, resgate).
5. O NII usa o gap de reprecificação até 12 meses, sem crescimento do balanço.

## Dados ilustrativos usados no protótipo

- Curva gerada por Nelson-Siegel com parâmetros (β₀=13,42%, β₁=1,12%, β₂=−1,75%, λ=1,5), com o formato típico de hoje: curto ~14,4%, vale perto de 5A (~13,30%), leve alta até 13A.
- Contratos: DI1F27 a F33, F35, F37 e F40. DU aproximado por dias corridos × 252/365,25 (na versão real, contagem pelo calendário).
- Histórico de 60 pregões por passeio aleatório de nível e inclinação.
- Carteira simulada com posições de −80 a +210 R$ mi por vencimento; balanço de ALM com R$ 224 bi em ativos sensíveis.
