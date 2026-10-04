"""Radar de Economia ES — página inicial.

Rodar com:  streamlit run app/Home.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.dados import obter_dados
from src import config

st.set_page_config(page_title=config.TITLE, layout="wide")
st.title(config.TITLE)
st.caption("Despesas públicas do Espírito Santo — 2024 e 2025. Fonte: Portal de Dados Abertos do ES.")

df = obter_dados()

c1, c2, c3 = st.columns(3)
c1.metric("Registros carregados", f"{len(df):,}".replace(",", "."))
c2.metric("Período", f"{df['Data'].min():%m/%Y} a {df['Data'].max():%m/%Y}")
c3.metric("Unidades Gestoras", df["UnidadeGestora"].nunique())

st.info("Visão geral com filtros e indicadores: em construção. "
        "Veja a página **Dados e auditoria** para conferir a importação.")
