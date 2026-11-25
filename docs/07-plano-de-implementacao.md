# Plano de implementação — DI Curve Analytics

> Versão 1 · 24/11/2026. Guia de execução do projeto.

## 1. Objetivo e definição de pronto

**Objetivo:** um site público, com link no portfólio, que mostra a curva DI real atualizada sozinha todo dia, mede o risco de uma carteira simulada e simula cenários, com o design definido em `01-design-system.md`.

**O projeto está pronto para o portfólio quando:**
- [ ] O link abre em menos de 3 s no celular e no computador.
- [ ] A curva mostrada é a do último fechamento da B3, atualizada sem intervenção manual.
- [ ] Os PUs recalculados batem com os da B3 dentro de R$ 0,01 em todos os vencimentos.
- [ ] O motor de cálculo tem testes automatizados, e os testes rodam a cada commit.
- [ ] O repositório tem um README com GIF, explicação e instruções para rodar localmente.
- [ ] Cenários, simulador personalizado e ALM funcionam no navegador.
- [ ] A aba Dados e metodologia explica fontes, fórmulas e limitações.

## 2. Escopo

| Entra no MVP | Fica para depois |
|---|---|
| Curva DI de fechamento (histórico + diário) | Intradiário com atraso de 15 min (Fase 6) |
| Motor: PU, taxa, fator, flat-forward, forwards, spreads | Curva de títulos públicos (LTN/NTN-F) |
| DV01, key rate, duration, convexidade | EVE/NII por produto |
| Choques paralelos, inclinação, macro, personalizado | Tela "Sobre o projeto" (vira a página do README) |
| ALM visão geral com balanço simulado | Login, carteiras do usuário |
| Superfície 3D do histórico | Alertas e notificações |
| Aba Dados e metodologia | |

## 3. Fontes de dados (verificadas em 24/11/2026)

| Dado | Fonte | Como acessar | Observações |
|---|---|---|---|
| Ajustes do DI1 (taxa e PU por vencimento) | B3 | Biblioteca **PYield** (`pip install pyield`), que busca os dados da B3; histórico desde 1991 | Plano B: página "Ajustes do pregão" da B3. Guardar cópia local de tudo que for baixado. |
| DI1 intradiário | B3 via PYield | Dados com **atraso de 15 min** durante o pregão | Resolve a dúvida do "tempo real": vamos chamar de "intradiário com atraso", nunca de "tempo real". |
| CDI e Selic meta | BCB SGS | `api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=…&dataFinal=…` · série 432 = Selic meta | Desde 26/03/2025 é obrigatório filtrar por data, com no máximo 10 anos por consulta. A rota de "últimos N valores" vai até 20. CDI anualizado = série 4389 (Fase 2). |
| Feriados / dias úteis | ANBIMA | Biblioteca **bizdays** (calendário ANBIMA) ou o módulo de dias úteis do PYield | Usar uma e validar contra a outra nos testes. |

**Termos de uso da B3 (lidos em 25/11/2026).** Resumo para orientar o projeto, não é parecer jurídico:
1. [Termos do site](https://www.b3.com.br/pt_br/termos-de-uso-e-protecao-de-dados/termos-de-uso): os dados são para uso exclusivamente pessoal; reprodução, publicação ou distribuição do conteúdo depende de autorização prévia e por escrito da B3.
2. [Política de Consumo de Market Data](https://www.b3.com.br/data/files/0D/97/1F/B7/4CCFF91094DCD8F9AC094EA8/Politica%20de%20Consumo%20de%20Market%20Data%20B3%20V1.1.pdf), item 3.3.2: dados de fim de dia e com atraso podem aparecer em gráficos e tabelas informacionais, mas não se pode permitir download. Em site aberto, o atraso cobre só alguns campos (último preço, preço de referência ou variação, mínima e máxima, volume, contratos em aberto).
3. Mesma política, item 13 e Anexo I: criar taxas, índices ou "qualquer outro dado derivado" a partir desses dados exige consentimento da B3.

**Consequência:** "publicar só métricas derivadas" não resolve, porque a política também cobre dado derivado. Até a decisão 5 (seção 11), nenhum JSON calculado com dados da B3 vai para o repositório público: o job diário coleta, verifica e monta os arquivos, mas a publicação fica desligada. Os arquivos brutos continuam fora do Git (`data/raw/` no `.gitignore`).

## 4. Princípio do projeto: motor próprio, validado contra referência

O valor para o portfólio está no **motor de cálculo próprio**. O PYield entra só para **coletar dados** e como **referência nos testes**: o nosso flat-forward, os dias úteis e os PUs precisam bater com os dele e com os da B3. Assim o projeto mostra as contas e também a validação delas.

## 5. Arquitetura

```
GitHub Actions (agendado)          Repositório                      GitHub Pages / Vercel
──────────────────────────         ─────────────────────────        ─────────────────────
 após o fechamento:                engine/   motor (Python)          web/  (React + TS)
  1. ingest  → data/raw (local)    ingest/   coletores               lê data/api/*.json
  2. qa      → verificações        qa/       checagens               gráficos D3 + Three.js
  3. build   → data/api/*.json     data/api/ JSON por data-base      simulador em TS
  4. commit + deploy               tests/
```

- **Sem servidor na fase 1:** o job gera arquivos JSON estáticos e o site só lê esses arquivos. Custo zero e nada para manter no ar.
- **Simulador no navegador:** as contas de cenário são portadas para TypeScript (o `CenCustom` do protótipo já tem a lógica em JS). Testes garantem que Python e TypeScript dão o mesmo resultado.

### Contrato de dados (JSON por data-base)

```
data/api/
  latest.json                  → aponta para a última data-base
  2026-11-24/curve.json        → contratos: código, vencimento, DU, taxa, PU, Δ
  2026-11-24/vertices.json     → vértices padrão interpolados (1M…10A)
  2026-11-24/forwards.json
  2026-11-24/risk.json         → DV01, key rate, duration, convexidade (carteira simulada)
  2026-11-24/alm.json          → gap, EVE, NII (balanço simulado)
  2026-11-24/qa.json           → resultado das verificações
  history/surface-120d.json    → matriz prazo × data × taxa
```

## 6. Stack

| Camada | Escolha | Motivo |
|---|---|---|
| Linguagem do motor | Python 3.12 | Base do protótipo; é a linguagem do curso de CDIA |
| Dados | pandas · numpy · Parquet | Padrão de mercado |
| Coleta | PYield · requests | PYield já resolve B3 e BCB |
| Dias úteis | bizdays (ANBIMA) | Biblioteca madura, com validação cruzada |
| Testes | pytest · hypothesis (propriedades) | Ex.: PU→taxa→PU sempre volta ao mesmo valor |
| Qualidade | ruff · mypy · pre-commit | Código limpo conta no portfólio |
| Frontend | Vite · React · TypeScript | Fiel ao design, componentes reutilizáveis |
| Gráficos | D3 (2D) · Three.js (superfícies 3D) | Controle total do visual Dark Quant |
| CI/CD | GitHub Actions | Testes a cada push, job diário agendado |
| Hospedagem | GitHub Pages (ou Vercel) | Grátis, link público |

## 7. Fases

Estimativas em horas de trabalho focado, com apoio do Claude Code na escrita do código.

### Fase 0 — Fundação · ~4 h
- Criar o repositório `di-curve-analytics` no GitHub, com licença MIT, `.gitignore` e estrutura de pastas.
- Ambiente Python (uv ou venv), ruff, mypy, pytest, pre-commit.
- CI rodando lint e testes em cada push.
- **Pronto quando:** um teste de exemplo passa no CI.

### Fase 1 — Motor de cálculo · ~15 h
| Módulo | Conteúdo | Testes principais |
|---|---|---|
| `engine/calendario.py` | DU entre datas, próximo dia útil | Conferir 20 datas contra bizdays e PYield |
| `engine/curva.py` | PU↔taxa, fator de desconto, flat-forward, vértices padrão | PU→taxa→PU idempotente; flat-forward passa exatamente pelos vértices; forwards constantes entre vencimentos |
| `engine/forwards.py` | Forwards entre vencimentos, spreads | Forward de dois pontos reconstrói a taxa longa |
| `engine/risco.py` | DV01, key rate, duration, convexidade, reprecificação exata | DV01 numérico (bump de 1 bp) ≈ analítico; soma dos key rates ≈ DV01 paralelo |
| `engine/cenarios.py` | Paralelo, inclinação, macro, personalizado | Choque zero → ΔPV zero; simetria aproximada para choques pequenos |
| `engine/alm.py` | Gap, ΔEVE, ΔNII, duration gap | Balanço casado → ΔEVE ≈ 0 |
- Incluir casos de PU conferidos à mão como testes.
- **Pronto quando:** todos os testes passam e o motor bate com as referências externas (PYield e calendário ANBIMA do bizdays).

### Fase 2 — Dados reais · ~10 h
- `ingest/b3_di1.py`: ajustes do dia e backfill de 250 pregões.
- `ingest/bcb.py`: CDI e Selic com filtro de datas (limite de 10 anos por consulta).
- `qa/verificacoes.py`: as 6 verificações da aba de metodologia, com um relatório por dia.
- Armazenamento em Parquet particionado por data, com os brutos fora do Git.
- **Pronto quando:** a curva de 3 datas escolhidas bate com a B3 dentro de R$ 0,01 no PU.

### Fase 3 — Job diário e API estática · ~6 h
- `publish/api.py` gera os JSON do contrato de dados.
- A publicação depende da decisão 5 (termos da B3); enquanto isso, o job roda com a publicação desligada.
- Workflow agendado após o fechamento, para rodar sozinho todo dia útil.
- Se a coleta ou o QA falhar, o job **não** publica e mantém o último dia bom.
- **Pronto quando:** o job roda 5 dias úteis seguidos sem intervenção.

### Fase 4 — Frontend MVP · ~20 h
- Design system em código: tokens de cor e fonte e os componentes Panel, Stat, Seg, Table, Heat e Legend.
- Shell com Sidebar, Ticker e Rail.
- Telas: Overview e as 9 de Curva DI, incluindo a superfície 3D em Three.js (girável com o mouse).
- Mobile: menu empilhado e tabelas com rolagem.
- **Pronto quando:** Overview e Curva DI estão no ar com dados reais e o Lighthouse dá ≥ 90.

### Fase 5 — Frontend completo · ~20 h
- Sensibilidades (5 telas), Cenários (4 telas, com o simulador em TypeScript) e ALM.
- Aba Dados e metodologia, com os gráficos flat-forward × linear gerados a partir dos dados reais.
- Teste de paridade: o simulador em TS dá o mesmo resultado que o Python em 50 cenários aleatórios.
- **Pronto quando:** as 21 telas do design estão implementadas.

### Fase 6 — Intradiário com atraso · ~8 h
- Depende da decisão 5: a B3 tem regras próprias para distribuir dados com atraso em site aberto.
- Coleta a cada 15–30 min durante o pregão, mostrando "atualizado às hh:mm · atraso de 15 min".
- Ticker e curva do dia contra o fechamento anterior.
- **Pronto quando:** funciona por um pregão inteiro sem falhar.

### Fase 7 — Lançamento · ~6 h
- README do repositório com GIF, arquitetura, como rodar e decisões.
- Revisão de acessibilidade e desempenho.
- Divulgação: post e link no portfólio.

**Total estimado: ~89 h.**

## 8. Cronograma

| Ritmo | Duração | MVP no ar (Fases 0–4) | Completo (0–7) |
|---|---|---|---|
| 5 h/semana | ~18 semanas | ~11 semanas | ~18 semanas |
| 8 h/semana | ~11 semanas | ~7 semanas | ~11 semanas |
| 12 h/semana | ~8 semanas | ~5 semanas | ~8 semanas |

Cada fase termina com uma entrega visível: um teste passando, um gráfico com dado real ou uma tela no ar. Isso permite parar no meio e ainda ter algo para mostrar.

### Cronograma escolhido: ~5 h/semana (início na semana de 30/11/2026)

| Semanas | Fase | Entrega visível |
|---|---|---|
| 1 | 0 — Fundação | Repositório público com CI verde |
| 2–4 | 1 — Motor de cálculo | Motor testado reproduzindo o protótipo |
| 5–6 | 2 — Dados reais | Curva real batendo com a B3 |
| 7–8 | 3 — Job diário | Atualização automática por 5 dias seguidos |
| 9–12 | 4 — Frontend MVP | **Site no ar** com Overview e Curva DI (~meados de fevereiro de 2027) |
| 13–16 | 5 — Frontend completo | As 21 telas |
| 17 | 6 — Intradiário | Curva do dia com atraso de 15 min |
| 18 | 7 — Lançamento | README, post e currículo (~início de abril de 2027) |

Fim de ano e Carnaval devem atrasar uma ou duas semanas. Esse atraso já está considerado no "~".

**Andamento real:** as Fases 0 a 2 ficaram prontas em 24/11/2026, antes do início previsto. As semanas acima valem como teto para as fases seguintes.

## 9. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| B3 muda o formato ou a página e a coleta quebra | Site desatualizado | PYield como camada; cache local; QA bloqueia a publicação; alerta por e-mail quando o job falha |
| Termos de uso da B3 restringem a publicação | Ter que tirar dados do ar | Termos lidos em 25/11/2026 (seção 3): restringem publicação, download e dado derivado. Publicação desligada até a decisão 5 |
| Erro de cálculo passa despercebido | Credibilidade com quem é da área | Testes contra PYield e B3; testes de propriedade; casos de PU conferidos à mão |
| Agendamento do GitHub Actions atrasa | Atualização atrasa alguns minutos | Aceitável no fechamento; no intradiário, mostrar a hora real da coleta |
| 3D pesado no celular | Site lento | Versão 2D como alternativa no mobile; carregar o Three.js só nas telas que usam |
| Escopo cresce | Projeto não termina | MVP fechado (seção 2); itens novos vão para "depois" |
| Confusão com dados proprietários | Problema de compliance | Nenhum dado, carteira ou metodologia interna de qualquer instituição; tudo público ou simulado, e o README diz isso |

## 10. Como vamos trabalhar

1. Uma fase por vez, cada uma num branch com pull request.
2. O código é escrito com apoio do Claude Code; todo PR é revisado e aprovado pelo autor.
3. No fim de cada fase: demo curta, atualização deste plano (status) e registro de decisões novas em `05-decisoes.md`.
4. Os números novos são sempre conferidos contra uma referência antes de ir para a tela.

## 11. Decisões

| # | Decisão | Status |
|---|---|---|
| 1 | Horas por semana | ✅ ~5 h/semana |
| 2 | Repositório público ou privado | ✅ Público desde o primeiro commit |
| 3 | Nome do repositório e domínio | Proposta: `di-curve-analytics` no GitHub Pages |
| 4 | Hospedagem do frontend | Proposta: GitHub Pages; Vercel se precisar de algo dinâmico depois |
| 5 | Publicação de dados da B3 | ⏳ Pendente. Opções: pedir autorização por escrito à B3; publicar só gráficos, sem JSON para download; ou trocar a curva por uma fonte de dados abertos |

## 12. Status

| Fase | Status |
|---|---|
| Design (21 telas, design system, metodologia) | ✅ Concluída |
| 0 — Fundação | ✅ Concluída (PR #2) |
| 1 — Motor de cálculo | ✅ Concluída (PR #3) |
| 2 — Dados reais | 🔄 Em revisão (PR da fase 2). 250 pregões baixados e verificados: 0 reprovados, 0 divergências de DU, PU a até R$ 0,005 da B3 |
| 3 a 7 | — |

## Fontes
- PYield (coleta B3/ANBIMA/BCB, intradiário com 15 min de atraso): https://pypi.org/project/PYield
- API SGS do Banco Central (limites e formato): https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom
- bizdays (calendário ANBIMA): https://wilsonfreitas.github.io/python-bizdays/quick.html
- B3, boletins e termos de uso dos dados: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/
