# Registro de decisões

| # | Data | Decisão | Motivo |
|---|---|---|---|
| 1 | 16/11/2026 | Manter o estilo Dark Quant | Fundo escuro é o padrão das telas de mesa e soa profissional na área. |
| 2 | 16/11/2026 | Tirar neon, glow, onda de partículas e grids de cards iguais | São os sinais que dão "cara de IA" aos protótipos gerados por imagem. |
| 3 | 16/11/2026 | 3D só em superfícies com terceira dimensão real | 3D em curva do dia ou em barras distorce a leitura e quem é da área percebe. Superfície prazo × data × taxa vira o gráfico-assinatura. |
| 4 | 16/11/2026 | Títulos em Instrument Serif, números em Geist Mono, interface em Geist | Tipografia com personalidade é o que mais tira a cara de template. |
| 5 | 16/11/2026 | Anotações dentro dos gráficos em vez de KPIs com setinha | Mostram o raciocínio por trás do número. |
| 6 | 16/11/2026 | Um único motor de cálculo para todas as telas | Os protótipos antigos tinham PUs inventados (ex.: DI1F50 com PU 75.128, quando o correto seria ~5.600) e indicadores que não batiam com as tabelas. |
| 7 | 16/11/2026 | Cenários reprecificam exatamente, sem aproximação por duration | É o que uma mesa faz na prática; a aproximação aparece só na tela de convexidade, para comparação. |
| 8 | 16/11/2026 | Flat-forward base 252 como interpolação | Padrão do mercado brasileiro; mantém forwards constantes entre vencimentos. |
| 9 | 16/11/2026 | Logo = formato da curva do dia | Assinatura visual própria, ligada ao dado. |
| 10 | 23/11/2026 | Criar a aba Dados e metodologia com gráfico para cada fórmula | Credibilidade para quem é da área e didática para quem não é. |
| 11 | 24/11/2026 | Planejar tudo antes de implementar (`07-plano-de-implementacao.md`) | A fonte de dados é o maior risco; escolher errado obrigaria a refazer muita coisa. |
| 12 | 24/11/2026 | Motor de cálculo próprio; PYield só para coleta e como referência nos testes | O valor do projeto está nas contas próprias, validadas contra uma referência externa. |
| 13 | 24/11/2026 | "Intradiário com atraso de 15 min", nunca "tempo real" | É o que os dados públicos permitem; prometer tempo real seria impreciso. |
| 14 | 24/11/2026 | Ritmo de ~5 h/semana | Disponibilidade do autor; MVP em ~11 semanas, completo em ~18. |
| 15 | 24/11/2026 | Repositório público desde o primeiro commit | O histórico de commits também conta como portfólio. |
| 16 | 24/11/2026 | Não versionar dados brutos da B3; publicar só métricas derivadas | Respeitar os termos de uso dos dados da B3. |
| 17 | 24/11/2026 | Feriados calculados por regra (datas fixas + Páscoa), sem arquivo externo | Função pura e auditável; conferida contra a lista da ANBIMA de 2001 a 2078. |
| 18 | 24/11/2026 | Usar a lista de feriados vigente na data-base (20/11 só a partir de 26/12/2023) | Um DU calculado antes da lei não descontava o 20/11; sem essa regra os PUs históricos não batem. Mesma convenção do PYield. |
| 19 | 24/11/2026 | Key rate com alocação triangular, em vez de vértice mais próximo | A soma dos key rates fica exatamente igual ao DV01 paralelo. |
| 20 | 24/11/2026 | Critério de pronto da Fase 1: validação contra PYield e bizdays, não contra o protótipo | Uma referência externa independente é uma prova mais forte que o próprio protótipo. |
| 21 | 24/11/2026 | Séries do BCB: 4389 (CDI anualizado) e 432 (meta Selic), em janelas de até 10 anos | Limite da API SGS; as duas séries cobrem o carrego e a âncora curta da curva. |
| 22 | 24/11/2026 | Verificações com gravidade: "erro" bloqueia o dia, "alerta" só registra | Variação grande é informação de mercado, não defeito do dado. |
| 23 | 24/11/2026 | Alerta de variação diária em 50 bps, não 25 | Medido em 250 pregões: 25 bps gerava alerta a cada nove dias; 50 bps só nos 4 dias de choque real. |
| 24 | 24/11/2026 | Falha no BCB não bloqueia a curva | A curva vem só da B3; CDI e Selic são contexto e podem ser repostos no dia seguinte. |
| 25 | 24/11/2026 | 24/12 e 31/12 são dias úteis sem pregão | A B3 não abre nesses dias, mas eles contam no DU (mesma regra da B3 no DU dos contratos). |
| 26 | 25/11/2026 | Carteira simulada definida por prazo constante (3M a 12A), não por código de contrato | Contratos vencem; por prazo, a carteira é a mesma todo dia e o risco muda só pela curva. |
| 27 | 25/11/2026 | Job diário às 21:17 (Brasília), com os brutos guardados no cache do Actions | Dá margem para a B3 divulgar os ajustes; o cache não é baixável pelo site do GitHub, então os brutos não ficam públicos. |
| 28 | 25/11/2026 | Publicação desligada até a decisão 5; o job coleta, verifica e monta os JSON, mas não versiona nada | Os termos da B3 restringem publicação, download e dado derivado (plano, seção 3). |
| 29 | 25/11/2026 | `latest.json` é gravado por último e só se as verificações forem aprovadas | O site nunca lê um dia pela metade nem um dia reprovado. |
