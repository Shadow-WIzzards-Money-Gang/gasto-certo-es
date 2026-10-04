"""Gasto Certo ES — página inicial.

Rodar com:  streamlit run app/Home.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.dados import brl, brl_curto, obter_classificado, obter_dados  # noqa: E402
from src import config  # noqa: E402
from src import indicadores as ind  # noqa: E402

ANO_BASE, ANO_COMPARA = 2024, 2025
DESCONTO_REFERENCIA = 0.10   # mesma hipótese padrão do simulador da página 2

st.set_page_config(page_title=config.TITLE, layout="wide")
st.title(config.TITLE)
st.markdown("#### Onde o Estado do Espírito Santo perde dinheiro, e onde pode economizar")
st.caption("Para gestores da Fazenda, da Gestão e do controle interno. Dados oficiais de despesas "
           f"{ANO_BASE}–{ANO_COMPARA} do Portal de Dados Abertos do ES. Medida: **ValorPago**.")


@st.cache_data(show_spinner="Calculando o resumo...")
def _resumo() -> dict:
    """Números da Home, calculados uma vez e guardados em cache."""
    df = obter_classificado()
    ev = df[df["eh_juros_multa"]]
    dea = df[df["eh_dea"]]

    base = ind.base_compras(df)
    tab = ind.score_oportunidade(ind.indicadores_por_subelemento(base), min_ugs=5)
    top5 = tab["SubelementoDespesa"].head(5).tolist()
    _, economia = ind.simular_economia(tab, top5, DESCONTO_REFERENCIA, "dispensa")

    return {
        "juros": {a: float(ev.loc[ev["Ano"] == a, "ValorPago"].sum()) for a in (ANO_BASE, ANO_COMPARA)},
        "dea": {a: float(dea.loc[dea["Ano"] == a, "ValorPago"].sum()) for a in (ANO_BASE, ANO_COMPARA)},
        "ugs_juros": int(ev.loc[ev["Ano"] == ANO_COMPARA, "UnidadeGestora"].nunique()),
        "compras": float(base["ValorPago"].sum()),
        "dispensa": float(base.loc[base["eh_dispensa"], "ValorPago"].sum()),
        "n_score70": int((tab["Score"] >= 70).sum()),
        "top": tab[["SubelementoDespesa", "Score", "UGs", "Fornecedores"]].head(3),
        "economia_top5": economia,
        "registros": len(df),
        "periodo": f"{df['Data'].min():%m/%Y} a {df['Data'].max():%m/%Y}",
        "ugs": int(df["UnidadeGestora"].nunique()),
        "arquivos": int(df["arquivo_origem"].nunique()) if "arquivo_origem" in df else None,
    }


obter_dados()            # mostra erro amigável e para, se não houver dados
r = _resumo()

# ---------------------------------------------------------------- pergunta 1
st.divider()
st.subheader("1 · Gasto evitável")
st.caption("Quanto foi pago em juros, multas e encargos por atraso: dinheiro que não comprou nada.")
j0, j1 = r["juros"][ANO_BASE], r["juros"][ANO_COMPARA]
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Juros/multas pagos em {ANO_COMPARA}", brl_curto(j1), help=brl(j1),
          delta=(f"{j1 / j0 - 1:+.1%} vs {ANO_BASE}".replace(".", ",") if j0 > 0 else None), delta_color="inverse")
c2.metric(f"Juros/multas pagos em {ANO_BASE}", brl_curto(j0), help=brl(j0))
c3.metric(f"Unidades gestoras com juros/multas em {ANO_COMPARA}", r["ugs_juros"])
c4.metric(f"Despesas de exercícios anteriores {ANO_COMPARA}", brl_curto(r["dea"][ANO_COMPARA]),
          help=f"{brl(r['dea'][ANO_COMPARA])}. Indicador separado de falha de planejamento.")
st.page_link("pages/1_Gasto_evitavel.py", label="Ver ranking, alertas mensais e intervalos de confiança →")

# ---------------------------------------------------------------- pergunta 2
st.divider()
st.subheader("2 · Compras compartilhadas")
st.caption("Categorias compradas por muitas unidades, de muitos fornecedores, em pagamentos pequenos e por "
           "dispensa de licitação: candidatas a compra centralizada.")
d1, d2, d3, d4 = st.columns(4)
d1.metric(f"Valor pago em compras ({ANO_BASE}–{ANO_COMPARA})", brl_curto(r["compras"]), help=brl(r["compras"]))
d2.metric("Pago por dispensa de licitação", brl_curto(r["dispensa"]),
          f"{r['dispensa'] / r['compras']:.1%} das compras".replace(".", ",") if r["compras"] else None, delta_color="off")
d3.metric("Categorias com score ≥ 70", r["n_score70"])
d4.metric(f"Economia hipotética (top 5, {DESCONTO_REFERENCIA:.0%})", brl_curto(r["economia_top5"]),
          help="Hipótese: desconto de 10% sobre o valor pago por dispensa nas 5 categorias de maior score. "
               "Não é promessa. Ajuste o desconto no simulador da página 2.")
st.markdown("**Maiores oportunidades:** " + " · ".join(
    f"{row.SubelementoDespesa.capitalize()} (score {row.Score:.0f}, {row.UGs} UGs, {row.Fornecedores} fornecedores)"
    for row in r["top"].itertuples()))
st.page_link("pages/2_Compras_compartilhadas.py", label="Ver ranking completo, simulador e registros →")

# ---------------------------------------------------------------- como usar + base
st.divider()
e1, e2 = st.columns(2)
with e1:
    st.subheader("Como usar")
    st.markdown(
        "1. **Escolha o recorte**: ano, unidade gestora ou tipo de compra, nos filtros de cada página.\n"
        "2. **Leia o indicador**: cards, gráficos e intervalos de confiança respondem à pergunta.\n"
        "3. **Confira a origem**: em *Ver registros*, cada número abre os pagamentos que o geraram, "
        "com download em CSV."
    )
with e2:
    st.subheader("Base de dados")
    st.markdown(
        f"- **{r['registros']:,}** registros de despesa · período **{r['periodo']}**\n".replace(",", ".") +
        f"- **{r['ugs']}** unidades gestoras" +
        (f" · **{r['arquivos']}** arquivos oficiais\n" if r["arquivos"] else "\n") +
        "- CPF de pessoa física mascarado; nenhum dado bancário carregado"
    )
    st.page_link("pages/3_Dados_e_auditoria.py", label="Ver auditoria da importação →")

st.caption("Limitações: os dados não têm quantidade nem preço unitário, então não é possível afirmar sobrepreço. "
           "A coluna Orgao vem vazia na fonte; a análise é por unidade gestora.")