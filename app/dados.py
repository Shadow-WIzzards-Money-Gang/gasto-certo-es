"""Carregamento dos dados tratados para o app, com cache e mensagens de erro amigáveis."""
import streamlit as st

from src import etl


@st.cache_data(show_spinner="Carregando dados tratados...")
def _carregar():
    return etl.carregar_processado()


def obter_dados():
    """Devolve o DataFrame tratado ou para a página com uma mensagem clara."""
    try:
        return _carregar()
    except etl.ErroImportacao as e:
        st.error(str(e))
        st.stop()
