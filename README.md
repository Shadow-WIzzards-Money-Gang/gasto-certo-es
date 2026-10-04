# Gasto Certo ES

Painel para gestores públicos do Espírito Santo responderem a duas perguntas com os dados oficiais de despesas de 2024 e 2025:

1. **Gasto evitável:** quanto o Estado perde com juros, multas e encargos por atraso, e isso mudou de 2024 para 2025?
2. **Compras compartilhadas:** quais categorias de gasto são compradas por muitas unidades, de muitos fornecedores, em pagamentos pequenos e por dispensa de licitação, e seriam candidatas a uma compra centralizada?

Cada número exibido pode ser rastreado até os pagamentos que o produziram.

- **App publicado:** [PREENCHER: link do Streamlit Community Cloud]
- **Público:** gestores da SEFAZ, da SEGER e do controle interno dos órgãos estaduais
- **Turma:** 2ESPH · **Integrantes:** Antonio Neto, Felipe Mendes, Mauro Carlos

---

## Principais resultados

| Pergunta | Achado |
|---|---|
| Gasto evitável | R$ 12,74 mi pagos em juros/multas em 2024 e R$ 11,82 mi em 2025 (−7,2%). O IC 95% da diferença das médias mensais vai de −R$ 878 mil a +R$ 713 mil: contém zero, então **não dá para afirmar que houve queda**. |
| Gasto evitável | 98% do valor são juros do parcelamento do PASEP, pagos pela SEFAZ (custo estrutural). O restante é pequeno e espalhado por 67 unidades; algumas passam do próprio limite em vários meses (IDAF: 6 meses em 2025). |
| Compras compartilhadas | R$ 3,10 bi pagos em compras de bens e serviços, 12,1% por dispensa de licitação. 16 de 119 categorias têm score de oportunidade ≥ 70. |
| Compras compartilhadas | Líder: serviços de apoio administrativo (72 unidades, 73 fornecedores, R$ 169,3 mi, 38,2% dos pagamentos por dispensa). Contraprova: gasolina é comprada por 74 unidades, mas de 5 fornecedores, e fica no fim do ranking. |

---

## Como executar localmente

Requer **Python 3.11 ou mais recente** (o projeto usa pandas 3).

```bash
git clone https://github.com/Shadow-WIzzards-Money-Gang/gasto-certo-es.git
cd gasto-certo-es

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app/Home.py
```

Na primeira abertura, o app roda o ETL sozinho: extrai os `.zip` de `data/raw/`, trata os dados e grava `data/processed/despesas.parquet` e `data/processed/auditoria.csv`. Isso leva cerca de 1 minuto. Nas próximas aberturas, ele usa o Parquet já gerado.

Para rodar o ETL manualmente (por exemplo, depois de trocar os arquivos de `data/raw/`):

```bash
python -m src.etl
```

Para gerar de novo a planilha de revisão das categorias de juros/multas (veja [Metodologia](#pergunta-1--gasto-evitável)):

```bash
python -m src.revisar_categorias
```

### Testes

```bash
pytest
```

São 23 testes, cobrindo:

- **ETL:** conversão de valores e datas, máscara de CPF, pipeline completo, soma preservada, arquivo rejeitado, pasta vazia.
- **Indicadores:** classificação e revisão manual, ICs com casos conhecidos, alertas, ranking, universo de compras, score e simulador.

---

## Deploy (Streamlit Community Cloud, gratuito)

1. Em [share.streamlit.io](https://share.streamlit.io), entre com o GitHub e clique em **Create app → Deploy a public app from GitHub**.
2. Preencha:
   - **Repository:** `Shadow-WIzzards-Money-Gang/gasto-certo-es`
   - **Branch:** `main`
   - **Main file path:** `app/Home.py`
3. Em **Advanced settings**, escolha **Python 3.12** e clique em **Deploy**.

O Parquet não fica no repositório: tem 138 MB, acima do limite de 100 MB por arquivo do GitHub. O app o gera na primeira abertura, a partir dos `.zip` versionados em `data/raw/`.

**Memória:** com os dados carregados, o app usa cerca de 1,2 GB, dentro do limite do plano gratuito. O ETL roda em um processo separado e libera a própria memória ao terminar.

---

## Dados

| Item | Descrição |
|---|---|
| Fonte | Portal de Dados Abertos do Governo do Espírito Santo, conjunto *Despesa* (dicionário de dados v1.0) |
| Arquivos | 8 `.zip` em `data/raw/`: `despesas_es_2024_completo_parte_01` a `04` e `despesas_es_2025_completo_parte_01` a `04` |
| Período | 02/01/2024 a 31/12/2025 |
| Registros | 505.950 (2024) + 586.208 (2025) = **1.092.158**, de 118 unidades gestoras |
| Formato | CSV com `;`, UTF-8 com BOM e vírgula decimal |
| Medida principal | `ValorPago`. Empenhado, liquidado, pago e restos a pagar nunca são somados entre si. |

### Regras de tratamento (ETL)

| Situação | Decisão |
|---|---|
| Arquivo `.zip` corrompido ou sem `.csv` | Rejeitado e registrado na auditoria; os demais seguem |
| Arquivo sem coluna obrigatória | Rejeitado e registrado na auditoria; os demais seguem |
| Nenhum arquivo válido / pasta vazia | Erro com mensagem clara |
| `ValorPago` vazio | Tratado como 0 (contado em `valores_vazios`) |
| `ValorPago` não numérico | Registro excluído (contado em `valores_invalidos`) |
| `Data` ilegível | Registro excluído (contado em `datas_invalidas`) |
| `Ano` ausente | Derivado de `Data` |
| Duplicados | Removidos por `Id` |
| Textos categóricos | Maiúsculas, sem espaços extras |
| CPF de pessoa física | Mascarado (`***.456.789-**`); CNPJ mantido |
| Dados bancários | Nunca carregados |

**Resultado da auditoria:** 1.092.158 registros lidos e válidos, com 0 duplicados, 0 valores inválidos e 0 datas inválidas. A auditoria por arquivo aparece na tela *Dados e auditoria*.

### Achados de qualidade dos dados

- **A coluna `Orgao` vem 100% vazia,** e o `CodigoOrgao` agrupa unidades diferentes (ex.: 45 = DETRAN e Polícia Militar). Por isso a análise é feita por **unidade gestora**.
- **Inexigibilidade aparece com dois rótulos** (`INEXIGÍVEL` e `INEXIGIBILIDADE DE LICITAÇÃO`), tratados como um só.
- **22.633 registros têm `ValorPago` negativo** (estornos). Eles foram mantidos.
- **Busca por palavra-chave classifica errado.** Procurar "juros" capturava R$ 90,8 mi; a revisão manual reduziu para R$ 24,6 mi. O que saiu: "equalização de juros", que é um subsídio, gratificações e auxílio-moradia. O que entrou: juros/multa de mora do INSS patronal.

---

## Metodologia

### Pergunta 1 — Gasto evitável

- **Classificação:**
  - A regra automática pega subelementos com `JUROS`, `MULTA`, `MORA` ou `ENCARGO` e exclui juros e encargos da dívida pública.
  - A revisão manual em `data/reference/categorias_juros_multas.csv` (63 subelementos, coluna `incluir` S/N) **prevalece sobre a regra**.
  - Despesas de exercícios anteriores (elemento 92) formam um indicador separado.
- **Série mensal:** soma de `ValorPago` por mês. Mês sem pagamento conta como R$ 0.
- **IC 95% da média mensal e da diferença 2025 − 2024:** calculado por bootstrap (5.000 reamostragens). O IC pela distribuição t gerava limite inferior negativo, porque poucos meses concentram o valor.
- **Alerta mensal:** dispara quando o mês passa do limite superior do intervalo de predição de 95% calculado com os 12 meses do ano anterior. Funciona para o total e para cada unidade gestora.

### Pergunta 2 — Compras compartilhadas

- **Universo:** elementos de compra de bens e serviços (30, 32, 33, 35, 37, 39, 40, 52), com `ValorPago > 0`.
- **Fora do universo:** concessionárias (energia, água), Correios, publicidade legal, locação de imóveis, condomínios e suprimento de fundos. Nesses casos, comprar junto não muda nada.
- **Indicadores por subelemento:** nº de unidades gestoras, nº de fornecedores (`IdFavorecido`), pagamentos, ticket mediano, % dos pagamentos por dispensa e % do valor já comprado via ata.
- **Dispensa:** só `DISPENSA DE LICITAÇÃO` conta. Inexigibilidade significa fornecedor único, e centralizar não muda isso.
- **Score 0–100:** média dos percentis de 4 componentes: nº de UGs, nº de fornecedores, ticket mediano baixo e % por dispensa. Entram as categorias compradas por pelo menos 5 UGs. Percentil em vez de min-max porque os dados são muito assimétricos.
- **ICs:** Wilson para a % de pagamentos por dispensa; bootstrap (2.000 reamostragens) para o ticket mediano.
- **Simulador:** economia = valor-base × desconto hipotético.
  - A base pode ser só o valor pago por dispensa (conservador) ou todo o valor da categoria (otimista).
  - O resultado aparece também como faixa de 5% a 20%.
  - É uma **hipótese**, não uma promessa.

---

## Arquitetura

```
data/raw/*.zip ──► src/etl.py ──► data/processed/despesas.parquet ──► src/classificacao.py ──► app/ (Streamlit)
  (8 arquivos)   extrai, valida,        + auditoria.csv               src/indicadores.py
                 converte, audita
```

O ETL e os cálculos ficam separados da interface, o que permite testá-los com `pytest`. O app roda o ETL automaticamente quando o Parquet não existe.

```
gasto-certo-es/
├── app/
│   ├── Home.py                         # resumo das duas perguntas e da base
│   ├── dados.py                        # carga com cache, ETL automático, formatação, privacidade
│   └── pages/
│       ├── 1_Gasto_evitavel.py         # série mensal, IC, alertas, ranking de UGs, registros
│       ├── 2_Compras_compartilhadas.py # score, simulador, detalhe por categoria, registros
│       └── 3_Dados_e_auditoria.py      # auditoria da importação e amostra dos dados
├── src/
│   ├── config.py                       # caminhos, formato dos CSVs, colunas
│   ├── etl.py                          # extração, leitura, limpeza, auditoria, Parquet
│   ├── classificacao.py                # flags de juros/multas e DEA
│   ├── indicadores.py                  # ICs, alertas, ranking, score, simulador
│   └── revisar_categorias.py           # gera a planilha de revisão manual
├── data/
│   ├── raw/                            # .zip oficiais (versionados)
│   ├── reference/                      # categorias_juros_multas.csv (revisão manual)
│   ├── interim/                        # CSVs extraídos (gerado, ignorado pelo git)
│   └── processed/                      # Parquet + auditoria (gerado, ignorado pelo git)
├── tests/                              # pytest
└── requirements.txt
```

### Telas

| Tela | O que mostra | Jornada |
|---|---|---|
| Home | Resumo das duas perguntas (2024 × 2025), maiores oportunidades, números da base | Ver o panorama e escolher a pergunta |
| Gasto evitável | Filtros de ano, unidade gestora e confiança; série mensal com limite de alerta; comparação fixa 2024 × 2025 com IC; ranking de UGs; categorias consideradas | Selecionar a UG, ver o mês em alerta e abrir os registros |
| Compras compartilhadas | Filtros de período, tipo de compra e mínimo de UGs; ranking de score; simulador; detalhe por categoria com IC; metodologia | Escolher a categoria, simular o desconto e conferir os pagamentos |
| Dados e auditoria | Auditoria por arquivo e amostra dos registros tratados | Entender de onde veio cada número |

**Rastreabilidade:** toda tabela de registros mostra Id, data, unidade gestora, subelemento, modalidade, valor e arquivo de origem. A soma é conferida com o número exibido e há download em CSV. Nomes de pessoas físicas aparecem ocultos.

**Tratamento de erro:**

- Sem dados processados, o app roda o ETL; se ele falhar, mostra o motivo.
- Filtro sem resultado mostra um aviso.
- Ano sem ano anterior não gera alerta.

---

## Limitações conhecidas

- **Sem quantidade nem preço unitário:** o score indica fragmentação, não sobrepreço.
- **Só 12 meses por ano:** os intervalos de confiança ficam largos.
- **A classificação de juros/multas depende da revisão manual** em `data/reference/categorias_juros_multas.csv`.
- **Os resultados valem para os arquivos de 2024–2025 fornecidos.** Sem dados de servidores ou área física, não há normalização por tamanho de unidade.
- **Nomes de colunas seguem o dicionário de dados v1.0.** Se o portal mudar o layout, ajuste `src/config.py`.