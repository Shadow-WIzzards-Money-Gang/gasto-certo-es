"""Configurações centrais do projeto: caminhos, formato dos CSVs e colunas usadas."""
from pathlib import Path

TITLE = "Gasto Certo ES"

# ---------------------------------------------------------------- caminhos
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_INTERIM = RAIZ / "data" / "interim"   # CSVs extraídos dos .zip
DIR_PROCESSED = RAIZ / "data" / "processed"
ARQ_PARQUET = DIR_PROCESSED / "despesas.parquet"
ARQ_AUDITORIA = DIR_PROCESSED / "auditoria.csv"

# ------------------------------------------------- formato dos CSVs oficiais
# Portal de Dados Abertos do ES: ponto e vírgula, UTF-8 com BOM, vírgula decimal.
CSV_SEP = ";"
CSV_ENCODING = "utf-8-sig"
CSV_ENCODING_ALTERNATIVO = "latin-1"  # usado só se a leitura em UTF-8 falhar

# ---------------------------------------------------------------- colunas
# Sem estas colunas o arquivo é rejeitado (as perguntas 1 e 2 dependem delas).
COLUNAS_OBRIGATORIAS = [
    "Data",
    "ValorPago",
    "Orgao",
    "UnidadeGestora",
    "ElementoDespesa",
    "SubelementoDespesa",
]

# Colunas carregadas quando existirem no arquivo (o resto é descartado na leitura
# para economizar memória). Nomes conforme o dicionário de dados v1.0.
COLUNAS_USADAS = COLUNAS_OBRIGATORIAS + [
    "Id",
    "Ano",
    "ValorEmpenho",
    "ValorLiquidado",
    "ValorRap",
    "CodigoOrgao",
    "CodigoUnidadeGestora",
    "CodigoElementoDespesa",
    "DescricaoElementoDespesa",
    "CodigoSubelementoDespesa",
    "TipoLicitacao",
    "IdFavorecido",
    "Favorecido",
    "TipoFavorecido",
    "CpfCnpjNis",
    "Funcao"
]

# Medidas monetárias. Empenhado, liquidado, pago e RAP são medidas DISTINTAS:
# o ETL converte cada uma, mas nunca as soma entre si.
COLUNAS_MOEDA = ["ValorEmpenho", "ValorLiquidado", "ValorPago", "ValorRap"]

# Colunas de texto categórico padronizadas (maiúsculas, sem espaços extras).
COLUNAS_TEXTO = [
    "Orgao",
    "UnidadeGestora",
    "ElementoDespesa",
    "DescricaoElementoDespesa",
    "SubelementoDespesa",
    "TipoLicitacao",
    "Funcao",
    "Favorecido",
]

# Qualquer coluna cujo nome contenha um destes termos é descartada (dados bancários).
TERMOS_COLUNAS_PROIBIDAS = ["banco", "agencia", "agência", "contacorrente", "conta_corrente"]
