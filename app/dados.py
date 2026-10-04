"""Carregamento dos dados tratados para o app, com cache e mensagens de erro amigáveis."""
import pandas as pd
import streamlit as st

from src import classificacao, etl


@st.cache_data(show_spinner="Carregando dados tratados...")
def _carregar():
    return etl.carregar_processado()


def obter_dados() -> pd.DataFrame:
    """Devolve o DataFrame tratado ou para a página com uma mensagem clara."""
    try:
        return _carregar()
    except etl.ErroImportacao as e:
        st.error(str(e))
        st.stop()


@st.cache_data(show_spinner="Classificando despesas...")
def _classificado() -> pd.DataFrame:
    # sem argumentos: evita o Streamlit ter que "hashear" milhões de linhas a cada clique
    return classificacao.marcar(_carregar())


def obter_classificado() -> pd.DataFrame:
    """Dados com as flags eh_juros_multa / eh_dea (classificação feita no app, não no ETL,
    para que a revisão manual valha sem rodar o ETL de novo)."""
    obter_dados()            # mostra erro amigável e para, se não houver dados
    return _classificado()


def para_exibir(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Prepara registros para mostrar ao usuário sem identificar pessoas físicas."""
    out = df[[c for c in colunas if c in df.columns]].copy()
    if "Favorecido" in out.columns and "CpfCnpjNis" in df.columns:
        pf = df["CpfCnpjNis"].astype("string").str.startswith("***", na=False)
        out.loc[pf, "Favorecido"] = "PESSOA FÍSICA (oculto)"
    return out


def brl(v: float) -> str:
    """1234567.8 -> 'R$ 1.234.567,80'."""
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl_curto(v: float) -> str:
    """Formato compacto para cards: R$ 301,2 mil | R$ 1,23 mi."""
    if abs(v) >= 1e9:
        t = f"{v / 1e9:.2f} bi"
    elif abs(v) >= 1e6:
        t = f"{v / 1e6:.2f} mi"
    elif abs(v) >= 1e3:
        t = f"{v / 1e3:.1f} mil"
    else:
        t = f"{v:.2f}"
    return "R$ " + t.replace(".", ",")
