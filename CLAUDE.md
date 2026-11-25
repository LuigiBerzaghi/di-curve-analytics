# Regras do repositório

Projeto: terminal da curva de juros pré (LTN e NTN-F, dados abertos do BCB), risco de taxa, cenários e ALM. Plano em `docs/07-plano-de-implementacao.md`; decisões em `docs/05-decisoes.md`.

## Idioma
- Documentação, mensagens de commit, nomes de testes e docstrings em português.
- Nomes de módulos e funções podem ser em português ou inglês, mas mantenha o padrão do módulo.

## Convenções financeiras (não mudar sem registrar em docs/05-decisoes.md)
- Base 252 dias úteis, capitalização exponencial, taxa em % a.a. internamente como fração (0.1350 = 13,50%).
- Face do DI1 = R$ 100.000 (`dicurve.FACE_DI1`); face de LTN e NTN-F = R$ 1.000; cupom da NTN-F = 10% a.a., R$ 48,808848 por semestre.
- Interpolação flat-forward entre vencimentos; curva por bootstrapping (LTN direto, NTN-F além da última LTN), com o CDI como vértice de 1 DU.
- Cenários reprecificam exatamente; aproximação por duration só para comparação.
- Choques em bps somados à taxa a.a.

## Código
- Python 3.12, tipado (mypy strict). Funções puras no `engine/`, sem I/O.
- `ingest/` é o único lugar que acessa a rede. Testes que acessam a rede levam `@pytest.mark.network`.
- Todo cálculo novo entra com teste. Sempre que possível, um teste de propriedade (hypothesis) e uma comparação com referência externa (PYield, B3 ou caso conferido à mão).
- Antes de commitar: `make check` (ruff, ruff format, mypy, pytest).

## Dados
- Fonte publicada: só dados abertos do BCB (licença ODbL), em `data/abertos/`; citar a fonte e manter a ODbL nos derivados.
- Dados da B3 (DI1) só para uso pessoal e validação local: nunca versionar (`data/raw/` no .gitignore) nem publicar nada calculado com eles. Testes com B3 levam `@pytest.mark.b3`.
- Nenhum dado ou metodologia interna de instituição financeira. Carteira e balanço são simulados.
- Nunca chamar os dados de "tempo real": o BCB publica o dia D na manhã de D+1.

## Fluxo
- Uma fase por branch (`fase-N-nome`) e PR. Ao fim da fase, atualizar a seção Status do plano e o README.
