# Design system — "Dark Quant contido"

## Direção

Dark Quant, só que sem os sinais que denunciam um gerador de imagem. O fundo escuro continua, porque é o padrão das telas de mesa (terminais e sistemas de tesouraria são quase todos escuros). Saem o neon, o brilho, as ondas de partículas decorativas e os grids de cards iguais.

**Princípios**

1. **Zero efeito decorativo.** Sem glow, gradiente, blur ou partícula. Hierarquia vem de tipografia, espaço e contraste.
2. **Um protagonista por tela.** Um gráfico grande e o resto mais discreto em volta, em vez de seis painéis do mesmo tamanho.
3. **Anotação em vez de KPI solto.** O gráfico explica a si mesmo ("vale da curva", "efeito convexidade") com linhas-guia finas e texto mono.
4. **3D só com uma terceira dimensão real.** Superfície prazo × data × taxa e superfície vencimento × choque × ΔPV. Curva do dia, barras de DV01 e gap são sempre 2D.
5. **Cor com significado.** Verde = alta/ganho/hoje, coral = queda/perda, âmbar = série secundária (forward, aproximação), cinza tracejado = fechamento anterior.

## Paleta

| Token | Hex | Uso |
|---|---|---|
| `BG` | `#0A0B0C` | Fundo de tudo |
| `LINE` | `#1D2023` | Linhas de grid, divisões entre painéis |
| `LINE2` | `#2B2F33` | Bordas de controles, linha do zero |
| `HOV` | `#121517` | Item ativo, hover, fundo de fórmula |
| `TXT` | `#E8EAE7` | Texto principal |
| `TXT2` | `#A7ADA9` | Texto de apoio |
| `TXT3` | `#8A908C` | Rótulos, eixos, metadados (passa 4,5:1 sobre o fundo) |
| `ACC` | `#7CD69E` | Cor principal: série de hoje, ganho, positivo |
| `NEG` | `#F07A68` | Negativo, perda |
| `AMB` | `#D9B06A` | Série secundária: forward, aproximação linear |
| `PREV` | `#6A716D` | Fechamento anterior (sempre tracejado) |
| azul de apoio | `#8DB4E2` | Quarta série em gráficos com várias linhas |

Superfície 3D sequencial: rampa de `#0E2A1E` (taxa baixa) a `#B4F0CB` (taxa alta). Superfície divergente: fundo até `ACC` (ganho) ou `NEG` (perda) pela magnitude.

## Tipografia

| Papel | Fonte | Uso |
|---|---|---|
| Títulos de página | **Instrument Serif** 48 px, peso 400 | O toque que tira a cara de template |
| Interface | **Geist** 12–14 px, pesos 400/500 | Rótulos, textos, navegação |
| Números | **Geist Mono** com `tabular-nums` | Tabelas, KPIs, eixos, breadcrumbs |

Breadcrumbs em mono maiúsculo com espaçamento de 0,12 em (ex.: `CURVA DI · ESTRUTURA`). Números negativos usam o sinal de menos tipográfico (−), não o hífen.

## Layout

- **Estrutura:** menu lateral de 232 px · faixa de cotações no topo · conteúdo · trilho direito de 320 px ("Movimentação da curva") nas telas de Curva, Sensibilidades e Overview.
- **Painéis sem cards arredondados:** blocos separados por linhas de 1 px (grid com `gap:1px` sobre fundo `LINE`), como um terminal.
- **Responsivo:** tudo em `flex-wrap`; no celular o menu empilha em cima e as tabelas rolam na horizontal.
- **Alvos de toque:** abas com 44 px de altura; seletores segmentados com 34 px.

## Componentes

| Componente | Descrição |
|---|---|
| Sidebar | Logo "Luigi" em serifa + mini-curva do dia em verde (a assinatura do projeto) + navegação |
| Ticker | Contratos DI1 principais, taxa e Δ em bps |
| Rail | Tabela de movimentação por prazo (curto, médio, longo), spreads e sparkline do vértice 2A |
| Stat | Rótulo, valor grande em mono, variação colorida |
| Panel | Título, subtítulo, controles à direita, conteúdo |
| Seg | Seletor segmentado (Taxa / Forward / PU, bps / %) |
| Heat | Mapa de calor com intensidade proporcional ao valor |
| Surface | Superfície 3D flutuante: base em grade, linhas de queda tracejadas, borda frontal destacada |

## Assinatura visual

O logo é o **formato da curva DI do dia**: uma mini-linha ao lado do nome, que muda todo dia. No cabeçalho da Overview, a superfície real dos últimos 40 pregões ocupa o lugar da onda decorativa dos protótipos antigos.
