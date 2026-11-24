# Regras do repositório

Projeto: terminal da curva DI (B3), risco de taxa, cenários e ALM. Plano em `docs/07-plano-de-implementacao.md`; decisões em `docs/05-decisoes.md`.

## Idioma
- Documentação, mensagens de commit, nomes de testes e docstrings em português.
- Nomes de módulos e funções podem ser em português ou inglês, mas mantenha o padrão do módulo.

## Convenções financeiras (não mudar sem registrar em docs/05-decisoes.md)
- Base 252 dias úteis, capitalização exponencial, taxa em % a.a. internamente como fração (0.1350 = 13,50%).
- Face do DI1 = R$ 100.000 (`dicurve.FACE_DI1`).
- Interpolação flat-forward entre vencimentos.
- Cenários reprecificam exatamente; aproximação por duration só para comparação.
- Choques em bps somados à taxa a.a.

## Código
- Python 3.12, tipado (mypy strict). Funções puras no `engine/`, sem I/O.
- `ingest/` é o único lugar que acessa a rede. Testes que acessam a rede levam `@pytest.mark.network`.
- Todo cálculo novo entra com teste. Sempre que possível, um teste de propriedade (hypothesis) e uma comparação com referência externa (PYield, B3 ou caso conferido à mão).
- Antes de commitar: `make check` (ruff, ruff format, mypy, pytest).

## Dados
- Nunca versionar dados brutos da B3 (`data/raw/` está no .gitignore). Publicar só métricas derivadas, citando a fonte.
- Nenhum dado ou metodologia interna de instituição financeira. Carteira e balanço são simulados.
- Usar "intradiário com atraso de 15 min", nunca "tempo real".

## Fluxo
- Uma fase por branch (`fase-N-nome`) e PR. Ao fim da fase, atualizar a seção Status do plano e o README.
