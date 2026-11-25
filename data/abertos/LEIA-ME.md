# Dados abertos da curva prefixada

Atualizados pelo job diário (`.github/workflows/diario.yml`, comando `dicurve-atualizar`).

| Arquivo | Conteúdo | Fonte | Licença |
|---|---|---|---|
| `titulos.csv` | Negociações definitivas de LTN e NTN-F no Selic, por dia e vencimento: operações, quantidade, PU mínimo/médio/máximo e taxas (só LTN). Taxas em fração. | Banco Central do Brasil, [Negociação de Títulos Federais no Mercado Secundário](https://dadosabertos.bcb.gov.br/dataset/negociacao-de-titulos-federais-no-mercado-secundario) (operações extragrupo) | ODbL |
| `cdi.csv` | CDI anualizado, base 252, em fração. | Banco Central do Brasil, SGS série 4389 | ODbL |

Formato: separador `;`, decimal `.`, datas ISO. Desde dez/2024.

Os dados do BCB estão sob a [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Estes recortes e os dados derivados deles publicados neste repositório também ficam sob a
ODbL, com a fonte citada.
