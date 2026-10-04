import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.dados import obter_dados  # noqa: E402
from src import etl  # noqa: E402

st.set_page_config(page_title="Dados e auditoria", layout="wide")
st.title("Dados e auditoria")
st.write("De onde vêm os números: arquivos carregados e o que foi removido em cada etapa.")

obter_dados()            # garante que o ETL já rodou (gera a auditoria)

try:
    aud = etl.carregar_auditoria()
except etl.ErroImportacao as e:
    st.error(str(e))
    st.stop()

st.subheader("Auditoria da importação")
st.dataframe(aud, width="stretch", hide_index=True)
st.caption("ValorPago vazio é tratado como 0 (nada pago no registro). ValorPago não numérico "
           "e datas ilegíveis são excluídos. Duplicados são removidos por Id. "
           "CPF de pessoa física é mascarado; dados bancários não são carregados.")

df = obter_dados()
st.subheader("Amostra dos registros tratados")
st.dataframe(df.head(200), width="stretch", hide_index=True)
