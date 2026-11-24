# DI Curve Analytics

[![CI](https://github.com/LuigiBerzaghi/di-curve-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/LuigiBerzaghi/di-curve-analytics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Terminal de análise da curva de juros pré brasileira (DI1). Ele monta a curva a partir dos ajustes da B3, mede o risco de taxa de uma carteira, simula cenários e mostra o efeito no balanço (ALM).

> 🚧 **Em construção.** O plano completo, com fases, cronograma e riscos, está em [`docs/07-plano-de-implementacao.md`](docs/07-plano-de-implementacao.md).

## O que vai ter

| Módulo | Pergunta que responde |
|---|---|
| **Curva DI** | Qual a forma da curva hoje? Quais forwards ela embute? Como PU, taxa e fator de desconto se relacionam? Como ela se moveu nos últimos meses? |
| **Sensibilidades** | Quanto a carteira ganha ou perde por bp (DV01)? Em que vértice está o risco (key rate)? Qual a duration e a convexidade? |
| **Cenários** | O que acontece com choques paralelos, mudanças de inclinação, cenários macro e choques montados vértice a vértice? |
| **ALM** | Qual o descasamento de prazos e o efeito no valor econômico (EVE) e na margem (NII)? |
| **Dados e metodologia** | De onde vêm os números, como a curva é montada e quais premissas sustentam cada métrica? |

## Andamento

| Fase | Status |
|---|---|
| Design (21 telas, design system, metodologia) | ✅ |
| 0 · Fundação (estrutura, ferramentas, CI) | 🔄 |
| 1 · Motor de cálculo | ⏳ |
| 2 · Dados reais | ⏳ |
| 3 · Atualização diária automática | ⏳ |
| 4 · Site no ar (Overview e Curva DI) | ⏳ |
| 5 · Todas as telas | ⏳ |
| 6 · Intradiário com 15 min de atraso | ⏳ |
| 7 · Lançamento | ⏳ |

## Estrutura

```
src/dicurve/
  engine/    motor de cálculo: calendário, curva, forwards, risco, cenários, ALM
  ingest/    coletores de dados públicos (B3, BCB, ANBIMA)
  qa/        verificações de qualidade dos dados
  publish/   geração dos JSON que o site lê
tests/       testes automatizados
data/api/    JSON publicados (os dados brutos nunca entram no Git)
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

## Documentação

- [Design system](docs/01-design-system.md)
- [Metodologia: convenções, fórmulas e premissas](docs/02-metodologia.md)
- [Registro de decisões](docs/05-decisoes.md)
- [Plano de implementação](docs/07-plano-de-implementacao.md)

## Fontes de dados

Os dados de mercado vêm de fontes públicas: B3 (ajustes do DI1), Banco Central (SGS) e ANBIMA (calendário de feriados). O repositório publica apenas métricas derivadas, com a fonte citada, e não redistribui os arquivos brutos.

## Aviso

Projeto pessoal e educacional. A carteira e o balanço usados nas telas de risco e ALM são **simulados**. Nenhum dado, carteira ou metodologia interna de qualquer instituição financeira é usado. Nada aqui é recomendação de investimento.
