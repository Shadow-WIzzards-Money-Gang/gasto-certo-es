"""Indicadores das perguntas 1 e 2.

Regra: empenhado, liquidado, pago e RAP nunca são somados entre si.
A medida da Pergunta 1 é sempre ValorPago.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

# ===================================================== Pergunta 1: gasto evitável


def serie_mensal(df: pd.DataFrame, anos: list[int]) -> pd.Series:
    """Soma de ValorPago por mês, com TODOS os meses dos anos pedidos (mês sem pagamento = 0).

    Preencher com zero é importante: ignorar meses vazios superestimaria a média.
    """
    meses = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-01", freq="MS")
    s = df.groupby("Mes")["ValorPago"].sum()
    return s.reindex(meses, fill_value=0.0).rename_axis("Mes")


@dataclass
class IC:
    media: float
    inf: float
    sup: float
    n: int


def ic_media(valores: pd.Series, confianca: float = 0.95) -> IC | None:
    """IC da média (distribuição t). None se houver menos de 2 observações."""
    v = pd.Series(valores).dropna().astype(float)
    n = len(v)
    if n < 2:
        return None
    m, ep = v.mean(), v.std(ddof=1) / np.sqrt(n)
    if ep == 0:
        return IC(m, m, m, n)
    inf, sup = stats.t.interval(confianca, n - 1, loc=m, scale=ep)
    return IC(m, inf, sup, n)


def ic_diferenca(a: pd.Series, b: pd.Series, confianca: float = 0.95) -> IC | None:
    """IC da diferença de médias (b - a), Welch. None se algum grupo tiver < 2 obs."""
    a, b = pd.Series(a).astype(float), pd.Series(b).astype(float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    va, vb = a.var(ddof=1) / na, b.var(ddof=1) / nb
    dif, ep = b.mean() - a.mean(), np.sqrt(va + vb)
    if ep == 0:
        return IC(dif, dif, dif, na + nb)
    gl = (va + vb) ** 2 / (va**2 / (na - 1) + vb**2 / (nb - 1))
    inf, sup = stats.t.interval(confianca, gl, loc=dif, scale=ep)
    return IC(dif, inf, sup, na + nb)


def limite_alerta(base: pd.Series, confianca: float = 0.95) -> float | None:
    """Limite superior do INTERVALO DE PREDIÇÃO de um mês, a partir do ano-base.

    Usamos predição (e não o IC da média) porque o alerta compara UM mês com o padrão:
    o IC da média é estreito demais e marcaria quase metade dos meses.
    limite = média + t * s * sqrt(1 + 1/n)
    """
    v = pd.Series(base).astype(float)
    n = len(v)
    if n < 2:
        return None
    t = stats.t.ppf(1 - (1 - confianca) / 2, n - 1)
    return float(v.mean() + t * v.std(ddof=1) * np.sqrt(1 + 1 / n))


def alertas_mensais(serie: pd.Series, ano: int, confianca: float = 0.95) -> pd.DataFrame:
    """Meses de `ano` acima do limite calculado com os 12 meses de `ano - 1`."""
    base = serie[serie.index.year == ano - 1]
    atual = serie[serie.index.year == ano]
    lim = limite_alerta(base, confianca)
    out = atual.rename("ValorPago").to_frame()
    out["limite"] = lim
    out["alerta"] = (out["ValorPago"] > lim) if lim is not None else False
    return out


def ranking_ugs(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Total pago por unidade gestora no ano e no anterior, variação e nº de registros."""
    d = df[df["Ano"].isin([ano - 1, ano])].assign(ValorPago=lambda x: x["ValorPago"].astype(float))
    tot = d.pivot_table(index="UnidadeGestora", columns="Ano", values="ValorPago",
                        aggfunc="sum", fill_value=0.0)
    for a in (ano - 1, ano):
        if a not in tot.columns:
            tot[a] = 0.0
    n = d[d["Ano"] == ano].groupby("UnidadeGestora").size()
    r = pd.DataFrame({
        f"Pago {ano - 1}": tot[ano - 1],
        f"Pago {ano}": tot[ano],
        "Registros": n.reindex(tot.index, fill_value=0).astype(int),
    })
    ant = r[f"Pago {ano - 1}"]
    r["Variação %"] = np.where(ant > 0, (r[f"Pago {ano}"] / ant.where(ant > 0) - 1) * 100, np.nan)
    return r.sort_values(f"Pago {ano}", ascending=False).reset_index()


def ugs_com_alerta(df: pd.DataFrame, ano: int, confianca: float = 0.95) -> pd.DataFrame:
    """Para cada UG: nº de meses de `ano` acima do limite do ano anterior."""
    linhas = []
    for ug, g in df.groupby("UnidadeGestora"):
        al = alertas_mensais(serie_mensal(g, [ano - 1, ano]), ano, confianca)
        if al["alerta"].any():
            linhas.append({"UnidadeGestora": ug, "Meses em alerta": int(al["alerta"].sum()),
                           "Pago nos meses em alerta": float(al.loc[al["alerta"], "ValorPago"].sum())})
    cols = ["UnidadeGestora", "Meses em alerta", "Pago nos meses em alerta"]
    return pd.DataFrame(linhas, columns=cols).sort_values("Pago nos meses em alerta", ascending=False)


# ================================================ Pergunta 2: compras compartilhadas
# TODO: indicadores_por_subelemento, score_oportunidade, ic_bootstrap_mediana,
#       ic_wilson, simular_economia
