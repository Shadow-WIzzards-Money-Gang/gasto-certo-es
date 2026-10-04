"""Pergunta 2 — Onde comprar junto (compra centralizada) economizaria?"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.dados import brl, brl_curto, obter_dados, para_exibir  # noqa: E402
from src import indicadores as ind  # noqa: E402


def rs(v: float) -> str:
    """brl_curto para textos em markdown: escapa o "$" (o Streamlit lê $...$ como fórmula LaTeX)."""
    return brl_curto(v).replace("$", "\\$")


def pct(v: float) -> str:
    """38.25 -> '38,2%'."""
    return f"{v:.1f}%".replace(".", ",")


AZUL = "#2a78d6"

st.set_page_config(page_title="Compras compartilhadas", layout="wide")
st.title("Compras compartilhadas")
st.caption("Quais categorias de gasto são compradas por muitas unidades gestoras, de muitos fornecedores, "
           "em pagamentos pequenos e por dispensa de licitação? São as candidatas a uma **compra centralizada** "
           "(ata de registro de preços). Medida: **ValorPago**.")


@st.cache_data(show_spinner="Montando a base de compras...")
def _base_compras() -> pd.DataFrame:
    # sem argumentos: o Streamlit não precisa "hashear" o DataFrame inteiro a cada clique
    return ind.base_compras(obter_dados())


obter_dados()                      # mostra erro amigável e para, se não houver dados
base_total = _base_compras()

# ---------------------------------------------------------------- filtros
f1, f2, f3 = st.columns([1, 3, 1])
periodo = f1.selectbox("Período", ["2024 e 2025", "2024", "2025"])
nomes_el = {f"{k} · {v}": k for k, v in ind.ELEMENTOS_COMPRAVEIS.items()}
el_sel = f2.multiselect("Tipos de compra (elemento de despesa)", list(nomes_el), default=list(nomes_el))
min_ugs = f3.slider("Mín. de UGs compradoras", 2, 30, 5,
                    help="Comprar junto só faz sentido se várias unidades compram a mesma coisa.")

anos = [2024, 2025] if periodo == "2024 e 2025" else [int(periodo)]
base = base_total[base_total["Ano"].isin(anos)
                  & base_total["CodigoElementoDespesa"].astype("string").str.strip().isin([nomes_el[e] for e in el_sel])]

if not el_sel or base.empty:
    st.info("Nenhuma compra para os filtros escolhidos. Selecione ao menos um tipo de compra.")
    st.stop()

tab = ind.score_oportunidade(ind.indicadores_por_subelemento(base), min_ugs)
if tab.empty:
    st.info(f"Nenhuma categoria é comprada por {min_ugs} ou mais unidades gestoras. Diminua o mínimo de UGs.")
    st.stop()

# ---------------------------------------------------------------- cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valor pago em compras", brl_curto(base["ValorPago"].sum()), help=brl(base["ValorPago"].sum()))
c2.metric("Pago por dispensa de licitação", brl_curto(base.loc[base["eh_dispensa"], "ValorPago"].sum()),
          f"{base.loc[base['eh_dispensa'], 'ValorPago'].sum() / base['ValorPago'].sum():.1%} do valor",
          delta_color="off")
c3.metric("Categorias analisadas", len(tab), help=f"Compradas por {min_ugs}+ unidades gestoras.")
c4.metric("Categorias com score ≥ 70", int((tab["Score"] >= 70).sum()))
st.caption(f"Período: {periodo} · Pagamentos analisados: {len(base):,}".replace(",", ".") +
           " · Só elementos de compra de bens/serviços, ValorPago > 0. Concessionárias, imóveis e suprimento "
           "de fundos ficam fora (ver metodologia no fim da página).")

# ---------------------------------------------------------------- ranking
st.subheader("Ranking de oportunidade de compra centralizada")
top = tab.head(15).iloc[::-1]
hover = [
    f"<b>{r.SubelementoDespesa}</b><br>Score: {r.Score:.0f}<br>UGs compradoras: {r.UGs}"
    f"<br>Fornecedores distintos: {r.Fornecedores}<br>Ticket mediano: {brl(r.Ticket_mediano)}"
    f"<br>Pagamentos por dispensa: {r.Pct_pag_dispensa:.1f}%<br>Valor pago: {brl(r.Valor_pago)}"
    for r in top.itertuples()
]
fig = go.Figure(go.Bar(
    x=top["Score"], y=top["SubelementoDespesa"].str.slice(0, 55), orientation="h",
    marker=dict(color=AZUL, cornerradius=4), text=top["Score"].round(0).astype(int), textposition="outside",
    hovertext=hover, hoverinfo="text",
))
fig.update_layout(height=34 * len(top) + 70, margin=dict(l=10, r=30, t=10, b=10), bargap=0.3,
                  xaxis=dict(title="Score de oportunidade (0–100)", range=[0, 105],
                             gridcolor="rgba(128,128,128,0.15)"),
                  plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, width="stretch")

st.dataframe(
    tab[["SubelementoDespesa", "Score", "UGs", "Fornecedores", "Pagamentos", "Ticket_mediano",
         "Pct_pag_dispensa", "Pct_valor_ata", "Valor_pago", "Valor_dispensa"]],
    hide_index=True, width="stretch",
    column_config={
        "SubelementoDespesa": st.column_config.TextColumn("Categoria (subelemento)", width="large"),
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
        "UGs": st.column_config.NumberColumn("UGs compradoras"),
        "Fornecedores": st.column_config.NumberColumn("Fornecedores distintos"),
        "Ticket_mediano": st.column_config.NumberColumn("Ticket mediano", format="R$ %.2f"),
        "Pct_pag_dispensa": st.column_config.NumberColumn("% pagamentos por dispensa", format="%.1f%%"),
        "Pct_valor_ata": st.column_config.NumberColumn("% valor já via ata", format="%.1f%%",
                                                       help="Parte que já é comprada por adesão a ata de registro de preços."),
        "Valor_pago": st.column_config.NumberColumn("Valor pago", format="R$ %.2f"),
        "Valor_dispensa": st.column_config.NumberColumn("Valor por dispensa", format="R$ %.2f"),
    },
)
st.caption("Score = média de 4 percentis entre as categorias: nº de UGs compradoras, nº de fornecedores, "
           "ticket mediano baixo e % de pagamentos por dispensa. **% valor já via ata** alto indica que parte "
           "da categoria já é comprada de forma centralizada.")

# ---------------------------------------------------------------- simulador
st.subheader("Simulador de economia")
st.warning("⚠ **Hipótese, não promessa.** O desconto de uma compra centralizada é uma suposição do usuário. "
           "Os dados não têm quantidade nem preço unitário, então não é possível medir sobrepreço.")
s1, s2 = st.columns([3, 2])
cats = s1.multiselect("Categorias a centralizar", tab["SubelementoDespesa"].tolist(),
                      default=tab["SubelementoDespesa"].head(5).tolist())
desconto = s2.slider("Desconto hipotético da compra centralizada", 0, 30, 10, format="%d%%") / 100
modo = s2.radio("Sobre qual valor aplicar o desconto?",
                ["Só o valor pago por dispensa (conservador)", "Todo o valor da categoria (otimista)"])
base_sim = "dispensa" if modo.startswith("Só") else "total"

if not cats:
    st.info("Escolha ao menos uma categoria para simular.")
else:
    valor_base, economia = ind.simular_economia(tab, cats, desconto, base_sim)
    _, eco_min = ind.simular_economia(tab, cats, 0.05, base_sim)
    _, eco_max = ind.simular_economia(tab, cats, 0.20, base_sim)
    m1, m2, m3 = st.columns(3)
    m1.metric("Valor-base", brl_curto(valor_base), help=brl(valor_base))
    m2.metric(f"Economia estimada ({desconto:.0%})", brl_curto(economia), help=brl(economia))
    m3.metric("Faixa com desconto de 5% a 20%", f"{rs(eco_min)} – {rs(eco_max)}")
    st.caption(f"Economia = valor-base × desconto · {len(cats)} categoria(s) · Período: {periodo}. "
               "Valor-base conservador = só o que foi pago por dispensa, a parte comprada sem competição.")

# ---------------------------------------------------------------- detalhe + rastreabilidade
st.subheader("Detalhe de uma categoria")
cat = st.selectbox("Categoria", tab["SubelementoDespesa"].tolist())
conf = st.select_slider("Confiança", options=[0.90, 0.95, 0.99], value=0.95, format_func=lambda x: f"{x:.0%}")
regs = base[base["SubelementoDespesa"] == cat]
linha = tab.set_index("SubelementoDespesa").loc[cat]

ic_p = ind.ic_wilson(int(regs["eh_dispensa"].sum()), len(regs), conf)
ic_t = ind.ic_bootstrap_mediana(regs["ValorPago"], conf)

d1, d2, d3, d4 = st.columns(4)
d1.metric("Score", f"{linha['Score']:.0f}")
d2.metric("UGs compradoras", int(linha["UGs"]))
d3.metric("Fornecedores distintos", int(linha["Fornecedores"]))
d4.metric("Valor pago", brl_curto(linha["Valor_pago"]), help=brl(linha["Valor_pago"]))

if ic_p:
    n_fmt = f"{ic_p.n:,}".replace(",", ".")
    st.markdown(f"- **Dispensa:** {pct(ic_p.media)} dos {n_fmt} pagamentos foram por dispensa de licitação "
                f"(IC {conf:.0%} de Wilson: **{pct(ic_p.inf)} a {pct(ic_p.sup)}**).")
if ic_t:
    st.markdown(f"- **Ticket mediano:** metade dos pagamentos foi de até **{rs(ic_t.media)}** "
                f"(IC {conf:.0%} por bootstrap: {rs(ic_t.inf)} a {rs(ic_t.sup)}).")
st.caption("Os ICs tratam os pagamentos do período como amostra do processo de compra da categoria. "
           "Com muitos pagamentos o intervalo fica estreito; com poucos, fica largo.")

por_ug = (regs.groupby("UnidadeGestora")
          .agg(Valor_pago=("ValorPago", "sum"), Pagamentos=("ValorPago", "size"),
               Fornecedores=("IdFavorecido", "nunique"), Pag_dispensa=("eh_dispensa", "sum"))
          .assign(Pct_dispensa=lambda x: x["Pag_dispensa"] / x["Pagamentos"] * 100)
          .drop(columns="Pag_dispensa").sort_values("Valor_pago", ascending=False).reset_index())
st.markdown(f"**Quem compra {cat.title()}** — {len(por_ug)} unidades gestoras")
st.dataframe(por_ug, hide_index=True, width="stretch",
             column_config={"Valor_pago": st.column_config.NumberColumn("Valor pago", format="R$ %.2f"),
                            "Pct_dispensa": st.column_config.NumberColumn("% por dispensa", format="%.1f%%")})

with st.expander(f"Ver os {len(regs):,} pagamentos de origem".replace(",", ".")):
    exib = para_exibir(regs.sort_values("ValorPago", ascending=False),
                       ["Id", "Data", "UnidadeGestora", "SubelementoDespesa", "TipoLicitacao",
                        "Favorecido", "ValorPago", "arquivo_origem"])
    st.write(f"Soma de ValorPago = **{brl(regs['ValorPago'].sum())}** (confere com o valor da categoria).")
    st.dataframe(exib.head(1000), hide_index=True, width="stretch",
                 column_config={"ValorPago": st.column_config.NumberColumn(format="R$ %.2f"),
                                "Data": st.column_config.DateColumn(format="DD/MM/YYYY")})
    if len(exib) > 1000:
        st.caption("Mostrando os 1.000 maiores. O download traz todos.")
    st.download_button("Baixar todos os pagamentos (CSV)",
                       exib.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="pagamentos_categoria.csv", mime="text/csv")

# ---------------------------------------------------------------- metodologia
with st.expander("Metodologia e limitações"):
    st.markdown(
        "- **Universo:** elementos de compra de bens e serviços (" +
        ", ".join(f"{k} {v}" for k, v in ind.ELEMENTOS_COMPRAVEIS.items()) +
        "). Folha, aposentadorias, transferências e dívida ficam fora.\n"
        "- **Dispensa** = `DISPENSA DE LICITAÇÃO`. **Inexigibilidade não conta**: significa fornecedor único, "
        "e comprar junto não muda isso. Na fonte ela aparece com dois rótulos (`INEXIGÍVEL` e "
        "`INEXIGIBILIDADE DE LICITAÇÃO`), tratados como um só.\n"
        "- **Fora do ranking** (comprar junto não gera economia):\n" +
        "\n".join(f"    - {k.title()}: {v}" for k, v in ind.NAO_CENTRALIZAVEIS.items()) +
        "\n    - Suprimento de fundos: adiantamento em dinheiro, não é compra\n"
        "- **Limitação principal:** sem quantidade e preço unitário, o score indica *fragmentação*, não sobrepreço. "
        "Uma categoria com score alto é candidata a estudo, não prova de desperdício.\n"
        "- **Fornecedores** são contados por `IdFavorecido`; pessoas físicas aparecem ocultas nos registros."
    )