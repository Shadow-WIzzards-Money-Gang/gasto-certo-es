# Gasto Certo ES

Painel para gestores públicos identificarem **gasto evitável** (juros, multas e encargos por atraso) e **oportunidades de compra compartilhada** nas despesas do Governo do Espírito Santo (2024–2025).

## Dados

- **Fonte:** Portal de Dados Abertos do Governo do ES — conjunto *Despesa* (dicionário de dados v1.0). [PREENCHER: link]
- **Formato esperado:** CSV com `;`, UTF-8 com BOM e vírgula decimal.
- Coloque os arquivos **não tratados** em `data/raw/`. O ETL gera `data/processed/despesas.parquet` e `data/processed/auditoria.csv`.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.etl

streamlit run app/Home.py

# testes
pytest
```

## Arquitetura

```
data/raw/*.csv ──► src/etl.py ──► data/processed/despesas.parquet ──► src/indicadores.py ──► app/ (Streamlit)
                      │
                      └──► data/processed/auditoria.csv
```

| Pasta / arquivo | Função |
|---|---|
| `src/config.py` | Caminhos, formato dos CSVs, colunas obrigatórias e usadas |
| `src/etl.py` | Leitura, validação, conversão, limpeza, auditoria e gravação do Parquet |
| `src/classificacao.py` | (em construção) flags de juros/multas, DEA e dispensa |
| `src/indicadores.py` | (em construção) indicadores, ICs, score e simulador |
| `app/` | Interface Streamlit (`Home.py` + `pages/`) |
| `tests/` | Testes com pytest |

## Regras de tratamento (ETL)

| Situação | Decisão |
|---|---|
| Arquivo sem coluna obrigatória | Arquivo rejeitado e registrado na auditoria; os demais seguem |
| Nenhum arquivo válido / pasta vazia | Erro com mensagem clara |
| `ValorPago` vazio | Tratado como 0 (contado em `valores_vazios`) |
| `ValorPago` não numérico | Registro excluído (contado em `valores_invalidos`) |
| `Data` ilegível | Registro excluído (contado em `datas_invalidas`) |
| `Ano` ausente | Derivado de `Data` |
| Duplicados | Removidos por `Id` |
| Textos categóricos | Maiúsculas, sem espaços extras |
| CPF de pessoa física | Mascarado (`***.456.789-**`); CNPJ mantido |
| Dados bancários | Nunca carregados |

Empenhado, liquidado, pago e restos a pagar são convertidos separadamente e **nunca somados entre si**.

## Limitações conhecidas

- Os dados não têm quantidade nem preço unitário: não é possível afirmar sobrepreço.
- A amostra didática é um recorte sistemático; seus totais não representam o Estado inteiro.
- Os nomes de colunas seguem o dicionário de dados v1.0; se o portal mudar o layout, ajuste `src/config.py`.
