"""Classificação das despesas para a Pergunta 1 (gasto evitável).

Regra automática (sugestão):
- juros/multas por atraso: Subelemento OU Elemento contém JUROS, MULTA, MORA ou ENCARGO
  e NÃO contém termos de dívida pública (juros da dívida não são "atraso").
- DEA: elemento 92 / "DESPESAS DE EXERCÍCIOS ANTERIORES" (indicador separado).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config

PALAVRAS_JUROS_MULTAS = ["JUROS", "MULTA", "MORA", "ENCARGO"]
PALAVRAS_EXCLUIR = ["DÍVIDA", "DIVIDA", "AMORTIZA", "FINANCIAMENTO", "OPERAÇÕES DE CRÉDITO",
                    "OPERACOES DE CREDITO", "ENCARGOS SOCIAIS", "PATRONA"]

ARQ_REVISAO = config.RAIZ / "data" / "reference" / "categorias_juros_multas.csv"

def _contem(serie: pd.Series, palavras: list[str]) -> pd.Series:
    padrao = "|".join(palavras)
    return serie.fillna("").astype("string").str.upper().str.contains(padrao, regex=True, na=False)


def sugerir_juros_multas(df: pd.DataFrame) -> pd.Series:
    """Regra automática por palavra-chave (sem revisão)."""
    texto = df["SubelementoDespesa"].fillna("") + " | " + df["ElementoDespesa"].fillna("")
    return _contem(texto, PALAVRAS_JUROS_MULTAS) & ~_contem(texto, PALAVRAS_EXCLUIR)


def marcar(df: pd.DataFrame, arq_revisao: Path = ARQ_REVISAO) -> pd.DataFrame:
    """Adiciona as colunas booleanas `eh_juros_multa` e `eh_dea`."""
    df = df.copy()
    if arq_revisao.exists():
        rev = pd.read_csv(arq_revisao, sep=";", dtype=str, encoding="utf-8-sig")
        incluir = set(rev.loc[rev["incluir"].str.strip().str.upper() == "S", "SubelementoDespesa"])
        df["eh_juros_multa"] = df["SubelementoDespesa"].isin(incluir)
        df.attrs["fonte_classificacao"] = f"revisão manual ({arq_revisao.name})"
    else:
        df["eh_juros_multa"] = sugerir_juros_multas(df)
        df.attrs["fonte_classificacao"] = "regra automática por palavra-chave (não revisada)"

    cod = df.get("CodigoElementoDespesa", pd.Series("", index=df.index)).astype("string").str.strip()
    df["eh_dea"] = (cod == "92") | _contem(df["ElementoDespesa"], ["EXERCÍCIOS ANTERIORES", "EXERCICIOS ANTERIORES"])
    df["eh_juros_multa"] = df["eh_juros_multa"] & ~df["eh_dea"]   # DEA é contado à parte
    return df
