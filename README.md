# DI Curve Analytics

[![CI](https://github.com/LuigiBerzaghi/di-curve-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/LuigiBerzaghi/di-curve-analytics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Terminal de análise da curva de juros pré brasileira. Ele monta a curva por bootstrapping a partir das LTN e NTN-F negociadas no mercado secundário (dados abertos do Banco Central), mede o risco de taxa de uma carteira, simula cenários e mostra o efeito no balanço (ALM).

> 🚧 **Em construção.** O plano completo, com fases, cronograma e riscos, está em [`docs/07-plano-de-implementacao.md`](docs/07-plano-de-implementacao.md).

## O que vai ter

| Módulo | Pergunta que responde |
|---|---|
| **Curva pré** | Qual a forma da curva hoje? Quais forwards ela embute? Como PU, taxa e fator de desconto se relacionam? Como ela se moveu nos últimos meses? |
| **Sensibilidades** | Quanto a carteira ganha ou perde por bp (DV01)? Em que vértice está o risco (key rate)? Qual a duration e a convexidade? |
| **Cenários** | O que acontece com choques paralelos, mudanças de inclinação, cenários macro e choques montados vértice a vértice? |
| **ALM** | Qual o descasamento de prazos e o efeito no valor econômico (EVE) e na margem (NII)? |
| **Dados e metodologia** | De onde vêm os números, como a curva é montada e quais premissas sustentam cada métrica? |

## Andamento

| Fase | Status |
|---|---|
| Design (21 telas, design system, metodologia) | ✅ |
| 0 · Fundação (estrutura, ferramentas, CI) | ✅ |
| 1 · Motor de cálculo | ✅ |
| 2 · Dados reais | ✅ |
| 3 · Atualização diária automática (dados abertos do BCB) | 🔄 |
| 4 · Site no ar (Overview e Curva) | ⏳ |
| 5 · Todas as telas | ⏳ |
| 6 · A definir (sem fonte aberta intradiária) | ⏳ |
| 7 · Lançamento | ⏳ |

## Estrutura

```
src/dicurve/
  engine/    motor de cálculo: calendário, curva, títulos (LTN, NTN-F, bootstrapping), forwards, risco, cenários, ALM
  ingest/    coletores: BCB (títulos e CDI); B3 só para validação local
  qa/        verificações de qualidade dos dados
  publish/   geração dos JSON que o site lê
  simulado.py  carteira e balanço simulados das telas de risco e ALM
tests/       testes automatizados
data/abertos/ dados abertos do BCB (ODbL), atualizados pelo job diário
data/api/    JSON do site, gerados a partir de data/abertos
web/         frontend (Vite + React + TypeScript, D3, Three.js)
docs/        design system, metodologia, decisões e plano
```

## Rodando localmente

```bash
git clone https://github.com/LuigiBerzaghi/di-curve-analytics
cd di-curve-analytics
python -m venv .venv && source .venv/bin/activate
make install   # instala o pacote em modo editável e os hooks de pre-commit
make check     # lint, tipos e testes
```

Dados reais (dados abertos do BCB, em `data/abertos/`):

```bash
dicurve-atualizar                     # baixa LTN, NTN-F e CDI e verifica o último dia
dicurve-publicar --destino data/api   # monta os JSON do site (só se o dia for aprovado)
pytest -m "network and not b3"        # testes contra o BCB
```

O código do DI1 da B3 (`dicurve-b3-atualizar`, `dicurve-b3-backfill`) continua no repositório para validação local e uso pessoal; nada calculado com dados da B3 é publicado.

## Documentação

- [Design system](docs/01-design-system.md)
- [Metodologia: convenções, fórmulas e premissas](docs/02-metodologia.md)
- [Registro de decisões](docs/05-decisoes.md)
- [Plano de implementação](docs/07-plano-de-implementacao.md)

## Fontes de dados

Tudo o que é publicado vem de **dados abertos do Banco Central do Brasil**, sob a [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/):

- [Negociação de Títulos Federais no Mercado Secundário](https://dadosabertos.bcb.gov.br/dataset/negociacao-de-titulos-federais-no-mercado-secundario): taxas e PUs de LTN e NTN-F negociadas no Selic;
- SGS, série 4389: CDI anualizado.

Os recortes e os dados derivados publicados aqui (`data/abertos/`, `data/api/`) também ficam sob a ODbL, com a fonte citada. Os ajustes do DI1 da B3 não são publicados: os termos da B3 restringem a publicação de dados de mercado e de dados derivados deles ([plano, seção 3](docs/07-plano-de-implementacao.md)).

## Aviso

Projeto pessoal e educacional. A carteira e o balanço usados nas telas de risco e ALM são **simulados**. Nenhum dado, carteira ou metodologia interna de qualquer instituição financeira é usado. Nada aqui é recomendação de investimento.
