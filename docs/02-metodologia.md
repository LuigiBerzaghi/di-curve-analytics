# Metodologia

## Convenções

| Item | Convenção |
|---|---|
| Base de dias | 252 dias úteis |
| Capitalização | Exponencial (composta) |
| Unidade de taxa | % a.a. |
| Valor de face | DI1: R$ 100.000 · LTN e NTN-F: R$ 1.000 |
| Interpolação | Flat-forward entre vencimentos |
| Choques | bps somados à taxa a.a. |
| Data-base | Fechamento D0 |
| Calendário | Feriados nacionais (lista da ANBIMA), com a lista **vigente na data-base**: o 20/11 só entra a partir de 26/12/2023 |
| Contagem de DU | Intervalo `[data-base, vencimento)` |
| Pontas da curva | Antes do 1º vértice, a taxa do 1º; depois do último, a taxa do último |

## Pipeline

1. **Coleta:** negociações de LTN e NTN-F no Selic e CDI (dados abertos do BCB), feriados pela regra da ANBIMA → taxas e PUs brutos
2. **Calendário:** dias úteis entre a data-base e cada vencimento → DU por contrato
3. **Vértices:** bootstrapping (CDI em 1 DU, LTN direto, NTN-F além da última LTN) e validação contra o PU divulgado → curva nos vencimentos
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

### Títulos públicos prefixados
```
LTN:    PU = 1.000 / (1 + i)^(DU/252)
NTN-F:  PU = Σ C / (1 + y)^(DUₖ/252) + 1.000 / (1 + y)^(DU_T/252)      C = 1.000 × (1,10^0,5 − 1) = 48,808848
```
A LTN é zero cupom: a taxa dela já é a taxa zero do vencimento. A NTN-F paga cupom em 1º/jan e 1º/jul; a taxa única `y` que reprecifica o PU é a *yield*, que mistura as taxas zero de todos os fluxos.

### Bootstrapping da curva pré
1. **CDI** como vértice de 1 DU: a LTN mais curta costuma vencer em 3 ou 4 meses, e sem âncora a curva repetiria essa taxa até hoje.
2. **LTN:** cada uma vira um vértice com a taxa média negociada no dia. Quando o BCB não divulga a taxa, ela sai do PU médio.
3. **NTN-F que vencem depois da última LTN**, da mais curta para a mais longa: os cupons anteriores são descontados pela curva já montada, e a taxa zero do vencimento é a que faz o PU da curva igual ao PU médio negociado (bisseção).
4. **NTN-F dentro da faixa das LTN** não entram na curva: viram uma checagem (o PU pela curva das LTN contra o PU negociado).

Entre os vértices, flat-forward. As NTN-F estendem a curva até ~10 anos (2.250 a 2.530 DU).

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
Vértices de key rate: 1A, 2A, 3A, 5A, 7A e 10A. O DV01 de cada posição é repartido entre os dois vértices vizinhos com peso linear no prazo (alocação triangular); fora dos extremos, vai todo para a ponta. Assim a soma dos key rates é exatamente o DV01 paralelo.

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

## Verificações da curva de títulos (todo dia)

| Verificação | Regra | Gravidade |
|---|---|---|
| Títulos suficientes | Ao menos 4 LTN e curva até 1.260 DU (5 anos) | erro |
| Banda de taxa | Taxas das LTN e yields das NTN-F entre 2% e 30% a.a. | erro |
| PU recalculado | PU da LTN pela taxa máxima a até R$ 0,01 do PU mínimo divulgado pelo BCB (mesma operação) | erro |
| Sem arbitragem | Todas as forwards entre vértices positivas | erro |
| NTN-F coerente | NTN-F dentro da faixa das LTN a até 25 bps da yield implícita na curva | alerta |
| Variação diária | Vértices de 1A a 10A variando até 50 bps contra o dia anterior | alerta |

**Resultado em 496 dias (02/12/2024 a 24/11/2026):** nenhum dia reprovado; 6.112 LTN com PU recalculado a no máximo R$ 0,0024 do BCB; mediana de 12 LTN e 5 NTN-F por dia. Alertas: 26 dias de NTN-F descolada (desvio mediano de 6,1 bps, p90 de 15,2 bps) e 12 dias de variação acima de 50 bps.

**Códigos excluídos:** o código Selic 950198 (principal separado da NTN-F) fica fora; ele tem a mesma data de vencimento, mas é outro instrumento.

## Verificações do DI1 (validação local, dados da B3)

| Verificação | Regra | Gravidade |
|---|---|---|
| Vértices completos | Todos os vencimentos com taxa e PU de ajuste | erro |
| Banda de taxa | Entre 2% e 30% a.a. | erro |
| Variação diária | Sinalizar acima de 50 bps contra o pregão anterior | alerta |
| Dias úteis | DU e vencimento do nosso calendário iguais aos da B3 | erro |
| PU recalculado | PU do motor a até R$ 0,01 do PU de ajuste da B3 | erro |
| Sem arbitragem | Todas as forwards entre vencimentos positivas | erro |

Mantidas para validar o motor contra a B3 localmente (uso pessoal). Um **erro** bloqueia o dia; um **alerta** só fica registrado. Variação grande quase sempre é mercado, não dado errado: nos 250 pregões de 18/11/2025 a 23/11/2026 houve 4 dias acima de 50 bps, todos movimentos da curva inteira (o maior, +265 bps em 26/10/2026). Com o limite antigo de 25 bps seriam 27 alertas, um a cada nove pregões.

**Dias sem pregão.** A B3 não abre em 24/12 e 31/12, mas esses dias contam como dia útil no calendário ANBIMA. A coleta pula esses dias; a contagem de DU continua a mesma.

**Resultado nos 250 pregões:** 11.157 contratos-dia, 0 divergências de DU ou vencimento, diferença máxima de PU de R$ 0,005.

## Premissas e limitações

1. A curva usa negociações reais de LTN e NTN-F (BCB); a carteira e o balanço são simulados.
   A carteira tem 10 posições por prazo constante (3M a 12A, de −80 a +210 R$ mi), reprecificadas todo dia na curva do dia; o balanço tem R$ 224 bi em ativos sensíveis em 5 faixas (`dicurve/simulado.py`).
2. Choques são instantâneos: sem rebalanceamento, carrego ou passagem de tempo.
3. O balanço de ALM é agregado por faixa e cada faixa é tratada no ponto médio.
4. Sem risco de base, spread de crédito ou opcionalidade (pré-pagamento, resgate).
5. O NII usa o gap de reprecificação até 12 meses, sem crescimento do balanço.

## Dados ilustrativos usados no protótipo

- Curva gerada por Nelson-Siegel com parâmetros (β₀=13,42%, β₁=1,12%, β₂=−1,75%, λ=1,5), com o formato típico de hoje: curto ~14,4%, vale perto de 5A (~13,30%), leve alta até 13A.
- Contratos: DI1F27 a F33, F35, F37 e F40. DU aproximado por dias corridos × 252/365,25 (na versão real, contagem pelo calendário).
- Histórico de 60 pregões por passeio aleatório de nível e inclinação.
- Carteira simulada com posições de −80 a +210 R$ mi por vencimento; balanço de ALM com R$ 224 bi em ativos sensíveis.
