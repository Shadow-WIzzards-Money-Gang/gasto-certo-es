"""Pergunta 1 — Quanto o Estado perde com juros, multas e encargos por atraso?"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.dados import brl, brl_curto, obter_classificado, para_exibir  # noqa: E402
from src import indicadores as ind

def rs(v: float) -> str:
    """brl_curto para textos em markdown: escapa o "$" (o Streamlit lê $...$ como fórmula LaTeX)."""
    return brl_curto(v).replace("$", "\\$")

AZUL, CINZA, CRITICO, FAIXA = "#2a78d6", "#8c8c8c", "#d03b3b", "rgba(140,140,140,0.18)"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ANO_BASE, ANO_COMPARA = 2024, 2025   # comparação estatística fixa do projeto

st.set_page_config(page_title="Gasto evitável", layout="wide")
st.title("Gasto evitável")
st.caption("Juros, multas e encargos pagos por atraso: dinheiro público que não comprou nenhum bem ou serviço. "
           "Medida: **ValorPago** (restos a pagar não são somados).")

df = obter_classificado()
evit = df[df["eh_juros_multa"]]

if evit.empty:
    st.warning("Nenhuma despesa classificada como juros/multas/encargos. "
               "Rode `python -m src.revisar_categorias` e confira a lista de subelementos.")
    st.stop()

# ---------------------------------------------------------------- filtros
anos = sorted(df["Ano"].unique())
f1, f2, f3 = st.columns([1, 3, 1])
ano = f1.selectbox("Ano de análise", anos[::-1], help="Comparado sempre com o ano anterior.")
ugs = ["Todas as unidades gestoras"] + sorted(evit["UnidadeGestora"].dropna().unique())
ug = f2.selectbox("Unidade gestora", ugs)
conf = f3.select_slider("Confiança", options=[0.90, 0.95, 0.99], value=0.95, format_func=lambda x: f"{x:.0%}")

recorte = evit if ug == ugs[0] else evit[evit["UnidadeGestora"] == ug]
recorte_dea = df[df["eh_dea"]] if ug == ugs[0] else df[df["eh_dea"] & (df["UnidadeGestora"] == ug)]
no_periodo = recorte[recorte["Ano"].isin([ano - 1, ano])]

if no_periodo.empty:
    st.info(f"Nenhum pagamento de juros/multas para **{ug}** em {ano - 1}–{ano}. "
            "Escolha outra unidade gestora ou outro ano.")
    st.stop()

st.caption(f"Classificação: {df.attrs.get('fonte_classificacao', 'regra automática')}")

# ---------------------------------------------------------------- cards
serie = ind.serie_mensal(recorte, [ano - 1, ano])
tot_atual = recorte.loc[recorte["Ano"] == ano, "ValorPago"].sum()
tot_ant = recorte.loc[recorte["Ano"] == ano - 1, "ValorPago"].sum()
alertas = ind.alertas_mensais(serie, ano, conf)
dea = recorte_dea.loc[recorte_dea["Ano"] == ano, "ValorPago"].sum()

tem_base = (ano - 1) in anos            # 2024 selecionado -> não há 2023 nos dados
if not tem_base:
    alertas["alerta"] = False           # sem ano anterior, não há base para alerta
    alertas["limite"] = None

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Juros/multas pagos em {ano}", brl_curto(tot_atual), help=brl(tot_atual),
          delta=(f"{(tot_atual / tot_ant - 1):+.1%} vs {ano - 1}" if tem_base and tot_ant > 0 else None),
          delta_color="inverse")
c2.metric(f"Pago em {ano - 1}", brl_curto(tot_ant), help=brl(tot_ant))
c3.metric("Meses em alerta", f"{int(alertas['alerta'].sum())} de 12")
c4.metric(f"DEA {ano}", brl_curto(dea),
          help=f"Despesas de exercícios anteriores: {brl(dea)}. Indicador separado: sinal de falha de planejamento. Não somado aos juros/multas.")

# ---------------------------------------------------------------- série mensal
st.subheader("Evolução mensal")
base = serie[serie.index.year == ano - 1]
atual = serie[serie.index.year == ano]
lim = alertas["limite"].iloc[0] if len(alertas) else None

fig = go.Figure()
if lim is not None:
    fig.add_trace(go.Scatter(x=MESES, y=[lim] * 12, mode="lines", line=dict(color=CINZA, width=1, dash="dot"),
                             name=f"Limite de alerta ({conf:.0%}, base {ano - 1})",
                             hovertemplate="Limite: R$ %{y:,.2f}<extra></extra>"))
if tem_base:
    fig.add_trace(go.Scatter(x=MESES, y=base.values, mode="lines+markers", name=str(ano - 1),
                             line=dict(color=CINZA, width=2), marker=dict(size=8),
                             hovertemplate=f"{ano - 1} · %{{x}}: R$ %{{y:,.2f}}<extra></extra>"))
fig.add_trace(go.Scatter(x=MESES, y=atual.values, mode="lines+markers", name=str(ano),
                         line=dict(color=AZUL, width=2), marker=dict(size=8),
                         hovertemplate=f"{ano} · %{{x}}: R$ %{{y:,.2f}}<extra></extra>"))
em_alerta = alertas[alertas["alerta"]]
if not em_alerta.empty:
    fig.add_trace(go.Scatter(x=[MESES[m.month - 1] for m in em_alerta.index], y=em_alerta["ValorPago"],
                             mode="markers", name="⚠ Mês em alerta",
                             marker=dict(color=CRITICO, size=13, symbol="diamond", line=dict(color="white", width=2)),
                             hovertemplate="⚠ ALERTA · %{x}: R$ %{y:,.2f}<extra></extra>"))
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
                  yaxis=dict(title="R$ pagos no mês", tickformat=",.0f", gridcolor="rgba(128,128,128,0.15)"),
                  legend=dict(orientation="h", y=-0.15), plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, width="stretch")
st.caption(f"Período: jan/{ano - 1}–dez/{ano} · Medida: soma de ValorPago · Filtro: {ug} · "
           f"Registros: {len(no_periodo):,}".replace(",", ".") +
           " · Mês sem pagamento conta como R$ 0. Alerta = mês acima do limite superior do intervalo de "
           f"predição calculado com os 12 meses de {ano - 1}.")

# ---------------------------------------------------------------- comparação estatística (fixa)
st.subheader(f"{ANO_COMPARA} foi diferente de {ANO_BASE}?")
st.caption(f"Esta comparação é sempre {ANO_BASE} × {ANO_COMPARA}, independente do ano escolhido no filtro. "
           "O filtro de unidade gestora e o nível de confiança continuam valendo.")

serie_cmp = ind.serie_mensal(recorte, [ANO_BASE, ANO_COMPARA])
base_cmp = serie_cmp[serie_cmp.index.year == ANO_BASE]
atual_cmp = serie_cmp[serie_cmp.index.year == ANO_COMPARA]

# avisa quando um único mês domina o ano (outlier): é o que distorce médias e intervalos
for nome_ano, s_ano in ((ANO_BASE, base_cmp), (ANO_COMPARA, atual_cmp)):
    mes_max, frac = ind.concentracao_maior_mes(s_ano)
    if mes_max is not None and frac >= 0.4:
        st.warning(f"⚠ Em {nome_ano}, **{MESES[mes_max.month - 1]}/{mes_max.year}** concentra **{frac:.0%}** do total "
                   "do ano. Confira os registros desse mês: pode ser um pagamento pontual grande "
                   "(ex.: acordo ou decisão judicial) ou uma categoria classificada errado.")

ic_a, ic_b = ind.ic_media_bootstrap(base_cmp, conf), ind.ic_media_bootstrap(atual_cmp, conf)
ic_d = ind.ic_diferenca_bootstrap(base_cmp, atual_cmp, conf)
if ic_a and ic_b and ic_d:
    tab = pd.DataFrame({
        "": [f"Média mensal {ANO_BASE}", f"Média mensal {ANO_COMPARA}", f"Diferença ({ANO_COMPARA} − {ANO_BASE})"],
        "Estimativa": [brl(ic_a.media), brl(ic_b.media), brl(ic_d.media)],
        f"IC {conf:.0%} inferior": [brl(ic_a.inf), brl(ic_b.inf), brl(ic_d.inf)],
        f"IC {conf:.0%} superior": [brl(ic_a.sup), brl(ic_b.sup), brl(ic_d.sup)],
    })
    st.dataframe(tab, hide_index=True, width="stretch")
    st.caption("A diferença pode ser negativa: significa redução.")

    # ---- leitura em português do que a tabela mostra
    quem = "nas unidades gestoras somadas" if ug == ugs[0] else f"em {ug.title()}"
    for a_, ic_ in ((ANO_BASE, ic_a), (ANO_COMPARA, ic_b)):
        st.markdown(
            f"- **Em {a_}**, o gasto típico com juros/multas {quem} ficou entre "
            f"**{rs(ic_.inf)}** e **{rs(ic_.sup)}** por mês, com {conf:.0%} de confiança "
            f"(média de {rs(ic_.media)})."
        )

    variacao = abs(ic_d.media)
    if ic_d.inf > 0:
        st.error(f"⚠ **Aumento estatisticamente claro.** De {ANO_BASE} para {ANO_COMPARA}, o gasto mensal típico subiu "
                 f"entre {rs(ic_d.inf)} e {rs(ic_d.sup)} por mês, com {conf:.0%} de confiança "
                 f"(aumento estimado de {rs(variacao)}/mês).")
    elif ic_d.sup < 0:
        st.success(f"✓ **Redução estatisticamente clara.** De {ANO_BASE} para {ANO_COMPARA}, o gasto mensal típico caiu "
                   f"entre {rs(-ic_d.sup)} e {rs(-ic_d.inf)} por mês, com {conf:.0%} de confiança "
                   f"(redução estimada de {rs(variacao)}/mês).")
    else:
        sentido = "queda" if ic_d.media < 0 else "alta"
        st.info(f"**Não dá para afirmar que houve mudança.** A estimativa é de {sentido} de "
                f"{rs(variacao)}/mês, mas o intervalo vai de {rs(ic_d.inf)} a "
                f"{rs(ic_d.sup)} e contém zero: a diferença pode ser só a oscilação normal entre os meses.")
else:
    st.info("Dados insuficientes para calcular os intervalos.")

# ---------------------------------------------------------------- ranking
if ug == ugs[0]:
    st.subheader(f"Ranking de unidades gestoras — {ano}")
    rk = ind.ranking_ugs(evit, ano)
    al = ind.ugs_com_alerta(evit, ano, conf)
    rk = rk.merge(al[["UnidadeGestora", "Meses em alerta"]], on="UnidadeGestora", how="left")
    rk["Meses em alerta"] = rk["Meses em alerta"].fillna(0).astype(int)
    rk["Alerta"] = rk["Meses em alerta"].map(lambda n: f"⚠ {n} mês(es)" if n else "—")

    top = rk.head(10).iloc[::-1]
    fig2 = go.Figure(go.Bar(x=top[f"Pago {ano}"], y=top["UnidadeGestora"], orientation="h",
                            marker=dict(color=AZUL, cornerradius=4),
                            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>"))
    fig2.update_layout(height=40 * len(top) + 60, margin=dict(l=10, r=10, t=10, b=10), bargap=0.35,
                       xaxis=dict(title=f"R$ pagos em juros/multas em {ano}", tickformat=",.0f",
                                  gridcolor="rgba(128,128,128,0.15)"),
                       plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, width="stretch")

    st.dataframe(
        rk.drop(columns=["Meses em alerta"]), hide_index=True, width="stretch",
        column_config={
            f"Pago {ano - 1}": st.column_config.NumberColumn(format="R$ %.2f"),
            f"Pago {ano}": st.column_config.NumberColumn(format="R$ %.2f"),
            "Variação %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    st.caption(f"{len(rk)} unidades gestoras com juros/multas em {ano - 1}–{ano}. "
               "Selecione uma no filtro acima para ver a série e os registros dela.")

# ---------------------------------------------------------------- rastreabilidade
st.subheader("Ver registros de origem")
opcoes = [f"{MESES[m.month - 1]}/{m.year}" + (" ⚠" if a else "") for m, a in zip(alertas.index, alertas["alerta"])]
escolha = st.selectbox("Mês", ["Ano inteiro"] + opcoes)
regs = recorte[recorte["Ano"] == ano]
if escolha != "Ano inteiro":
    mes = alertas.index[opcoes.index(escolha)]
    regs = regs[regs["Mes"] == mes]

if regs.empty:
    st.info("Nenhum pagamento de juros/multas neste mês para o filtro escolhido (valor do mês = R$ 0).")
else:
    exib = para_exibir(regs.sort_values("ValorPago", ascending=False),
                       ["Id", "Data", "UnidadeGestora", "ElementoDespesa", "SubelementoDespesa",
                        "Favorecido", "ValorPago", "arquivo_origem"])
    st.write(f"**{len(regs)} registros** · soma de ValorPago = **{brl(regs['ValorPago'].sum())}** "
             "(confere com o valor exibido acima).")
    st.dataframe(exib, hide_index=True, width="stretch",
                 column_config={"ValorPago": st.column_config.NumberColumn(format="R$ %.2f"),
                                "Data": st.column_config.DateColumn(format="DD/MM/YYYY")})
    st.download_button("Baixar estes registros (CSV)", exib.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=f"registros_juros_multas_{ano}.csv", mime="text/csv")

with st.expander("Quais categorias contam como juros/multas?"):
    cat = (evit.groupby(["ElementoDespesa", "SubelementoDespesa"])["ValorPago"]
           .agg(["count", "sum"]).rename(columns={"count": "Registros", "sum": "Total pago"})
           .sort_values("Total pago", ascending=False).reset_index())
    st.dataframe(cat, hide_index=True, width="stretch",
                 column_config={"Total pago": st.column_config.NumberColumn(format="R$ %.2f")})
