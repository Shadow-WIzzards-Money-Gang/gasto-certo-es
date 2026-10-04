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


def ic_media_bootstrap(valores: pd.Series, confianca: float = 0.95, n_boot: int = 5000,
                       semente: int = 42) -> IC | None:
    """IC da média por bootstrap percentil.

    Por que existe: o IC pela distribuição t é simétrico (média ± margem). Quando um ou
    dois meses são gigantes, a margem fica maior que a média e o limite inferior sai
    NEGATIVO, o que é impossível para um gasto. O bootstrap reamostra os próprios meses,
    então o intervalo nunca sai do intervalo dos dados (nunca negativo) e respeita a assimetria.
    """
    v = pd.Series(valores).dropna().astype(float).to_numpy()
    n = len(v)
    if n < 2:
        return None
    rng = np.random.default_rng(semente)
    medias = rng.choice(v, size=(n_boot, n), replace=True).mean(axis=1)
    a = (1 - confianca) / 2
    return IC(float(v.mean()), float(np.quantile(medias, a)), float(np.quantile(medias, 1 - a)), n)


def ic_diferenca_bootstrap(a: pd.Series, b: pd.Series, confianca: float = 0.95, n_boot: int = 5000,
                           semente: int = 42) -> IC | None:
    """IC da diferença de médias (b - a) por bootstrap percentil."""
    a = pd.Series(a).dropna().astype(float).to_numpy()
    b = pd.Series(b).dropna().astype(float).to_numpy()
    if len(a) < 2 or len(b) < 2:
        return None
    rng = np.random.default_rng(semente)
    dif = (rng.choice(b, (n_boot, len(b))).mean(axis=1) - rng.choice(a, (n_boot, len(a))).mean(axis=1))
    q = (1 - confianca) / 2
    return IC(float(b.mean() - a.mean()), float(np.quantile(dif, q)), float(np.quantile(dif, 1 - q)), len(a) + len(b))


def concentracao_maior_mes(serie_ano: pd.Series) -> tuple[pd.Timestamp | None, float]:
    """Mês com maior valor e a fração do total do ano que ele representa."""
    tot = float(serie_ano.sum())
    if tot <= 0:
        return None, 0.0
    return serie_ano.idxmax(), float(serie_ano.max() / tot)


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
#
# Pergunta: quais categorias de gasto (subelementos) são compradas por muitas unidades
# gestoras, de muitos fornecedores, em pagamentos pequenos e por dispensa de licitação?
# Essas são as candidatas a compra centralizada (ata de registro de preços).

# Elementos de despesa que são COMPRAS de bens/serviços (o resto é folha, aposentadoria,
# transferência, dívida... que não se "compra junto").
ELEMENTOS_COMPRAVEIS = {
    "30": "Material de consumo",
    "32": "Material/bem para distribuição gratuita",
    "33": "Passagens e locomoção",
    "35": "Serviços de consultoria",
    "37": "Locação de mão de obra",
    "39": "Outros serviços de terceiros - PJ",
    "40": "Serviços de TI - PJ",
    "52": "Equipamentos e material permanente",
}

MODALIDADE_DISPENSA = "DISPENSA DE LICITAÇÃO"
# Na fonte, inexigibilidade aparece com DOIS rótulos diferentes para o mesmo conceito.
MODALIDADES_INEXIGIBILIDADE = {"INEXIGÍVEL", "INEXIGIBILIDADE DE LICITAÇÃO"}
MODALIDADE_ATA = "ADESÃO À ATA DE REGISTRO DE PREÇOS"

# Categorias em que comprar junto não gera economia: fornecedor único/monopólio
# (concessionárias) ou objeto que não é padronizável. Ficam fora do ranking.
NAO_CENTRALIZAVEIS = {
    "SERVIÇOS DE ENERGIA ELÉTRICA": "concessionária (monopólio regional)",
    "SERVIÇOS DE ÁGUA E ESGOTO": "concessionária (monopólio regional)",
    "CORRESPONDÊNCIAS": "Correios (exclusividade legal)",
    "SERVIÇOS DE PUBLICIDADE LEGAL": "Diário Oficial (publicação obrigatória)",
    "LOCAÇÃO DE IMÓVEIS": "imóvel específico, não padronizável",
    "CONDOMÍNIOS": "taxa do prédio ocupado, não padronizável",
}
PREFIXOS_EXCLUIR = ("SUPRIMENTO DE FUNDOS",)  # adiantamentos em dinheiro, não são compras


def base_compras(df: pd.DataFrame, elementos: list[str] | None = None) -> pd.DataFrame:
    """Recorte de compras: elementos compráveis, ValorPago > 0, sem categorias não centralizáveis.

    Adiciona as flags eh_dispensa, eh_inexigivel e eh_ata.
    """
    elementos = elementos or list(ELEMENTOS_COMPRAVEIS)
    cod = df["CodigoElementoDespesa"].astype("string").str.strip()
    sub = df["SubelementoDespesa"].astype("string")
    filtro = (
        cod.isin(elementos)
        & (df["ValorPago"] > 0)
        & ~sub.isin(list(NAO_CENTRALIZAVEIS))
        & ~sub.str.startswith(PREFIXOS_EXCLUIR, na=False)
        & sub.notna()
    )
    b = df.loc[filtro].copy()
    mod = b["TipoLicitacao"].astype("string").str.strip() if "TipoLicitacao" in b else pd.Series("", index=b.index)
    b["eh_dispensa"] = (mod == MODALIDADE_DISPENSA).fillna(False).astype(bool)
    b["eh_inexigivel"] = mod.isin(list(MODALIDADES_INEXIGIBILIDADE)).fillna(False).astype(bool)
    b["eh_ata"] = (mod == MODALIDADE_ATA).fillna(False).astype(bool)
    return b


def indicadores_por_subelemento(b: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por subelemento com os indicadores de fragmentação."""
    b = b.assign(
        _vd=b["ValorPago"].where(b["eh_dispensa"], 0.0),
        _va=b["ValorPago"].where(b["eh_ata"], 0.0),
    )
    t = b.groupby("SubelementoDespesa").agg(
        Elemento=("ElementoDespesa", "first"),
        UGs=("UnidadeGestora", "nunique"),
        Fornecedores=("IdFavorecido", "nunique"),
        Pagamentos=("ValorPago", "size"),
        Pagamentos_dispensa=("eh_dispensa", "sum"),
        Ticket_mediano=("ValorPago", "median"),
        Valor_pago=("ValorPago", "sum"),
        Valor_dispensa=("_vd", "sum"),
        Valor_ata=("_va", "sum"),
    )
    t["Pct_pag_dispensa"] = t["Pagamentos_dispensa"] / t["Pagamentos"] * 100
    t["Pct_valor_dispensa"] = t["Valor_dispensa"] / t["Valor_pago"] * 100
    t["Pct_valor_ata"] = t["Valor_ata"] / t["Valor_pago"] * 100
    return t.reset_index()


def score_oportunidade(t: pd.DataFrame, min_ugs: int = 5) -> pd.DataFrame:
    """Score 0–100 de oportunidade de compra centralizada.

    Média de 4 componentes, cada um em percentil (0–1) entre as categorias analisadas:
      - Abrangência: nº de UGs que compram a categoria (mais UGs = mais a ganhar juntando)
      - Fragmentação: nº de fornecedores distintos (muitos = compra pulverizada)
      - Pulverização: ticket mediano BAIXO (muitos pagamentos pequenos)
      - Dispensa: % dos pagamentos feitos por dispensa de licitação
    Percentil (e não min-max) porque os dados são muito assimétricos: uma categoria com
    450 fornecedores esmagaria todas as outras numa escala min-max.
    Só entram categorias compradas por pelo menos `min_ugs` UGs.
    """
    t = t[t["UGs"] >= min_ugs].copy()
    if t.empty:
        return t.assign(Score=pd.Series(dtype=float))
    t["c_abrangencia"] = t["UGs"].rank(pct=True)
    t["c_fragmentacao"] = t["Fornecedores"].rank(pct=True)
    t["c_pulverizacao"] = (-t["Ticket_mediano"]).rank(pct=True)
    t["c_dispensa"] = t["Pct_pag_dispensa"].rank(pct=True)
    comps = ["c_abrangencia", "c_fragmentacao", "c_pulverizacao", "c_dispensa"]
    t["Score"] = t[comps].mean(axis=1) * 100
    return t.sort_values("Score", ascending=False).reset_index(drop=True)


def ic_wilson(k: int, n: int, confianca: float = 0.95) -> IC | None:
    """IC de Wilson para uma proporção k/n (em %). Melhor que o IC "normal" com p perto de 0 ou 1."""
    if n <= 0:
        return None
    z = stats.norm.ppf(1 - (1 - confianca) / 2)
    p = k / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    margem = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return IC(p * 100, float(max(0.0, centro - margem) * 100), float(min(1.0, centro + margem) * 100), n)


def ic_bootstrap_mediana(valores: pd.Series, confianca: float = 0.95, n_boot: int = 2000,
                         semente: int = 42) -> IC | None:
    """IC da mediana por bootstrap percentil (a mediana não tem fórmula simples de IC)."""
    v = pd.Series(valores).dropna().astype(float).to_numpy()
    n = len(v)
    if n < 2:
        return None
    rng = np.random.default_rng(semente)
    meds = np.array([np.median(rng.choice(v, n, replace=True)) for _ in range(n_boot)])
    a = (1 - confianca) / 2
    return IC(float(np.median(v)), float(np.quantile(meds, a)), float(np.quantile(meds, 1 - a)), n)


def simular_economia(t: pd.DataFrame, categorias: list[str], desconto: float,
                     base: str = "dispensa") -> tuple[float, float]:
    """Economia estimada = valor-base × desconto (HIPÓTESE, não promessa).

    base="dispensa": só o valor pago por dispensa (cenário conservador: é a parte comprada
                     sem competição e que uma ata centralizada substituiria);
    base="total":    todo o valor pago na categoria (cenário otimista).
    Devolve (valor_base, economia).
    """
    sel = t[t["SubelementoDespesa"].isin(categorias)]
    col = "Valor_dispensa" if base == "dispensa" else "Valor_pago"
    valor_base = float(sel[col].sum())
    return valor_base, valor_base * desconto
