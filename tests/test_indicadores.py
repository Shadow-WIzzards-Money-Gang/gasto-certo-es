import numpy as np
import pandas as pd
import pytest

from src import classificacao, indicadores as ind


def base(linhas):
    df = pd.DataFrame(linhas, columns=["Data", "UnidadeGestora", "ElementoDespesa", "SubelementoDespesa", "ValorPago"])
    df["Data"] = pd.to_datetime(df["Data"])
    df["Ano"] = df["Data"].dt.year
    df["Mes"] = df["Data"].dt.to_period("M").dt.to_timestamp()
    return df


# ------------------------------------------------------------ classificação
def test_classificacao_exclui_divida_e_separa_dea(tmp_path):
    df = base([
        ["2024-01-05", "A", "OBRIGAÇÕES TRIBUTÁRIAS", "MULTAS E JUROS POR ATRASO", 10],
        ["2024-01-05", "A", "JUROS SOBRE A DÍVIDA POR CONTRATO", "JUROS DA DÍVIDA", 999],
        ["2024-01-05", "A", "DESPESAS DE EXERCÍCIOS ANTERIORES", "JUROS DE DEA", 5],
        ["2024-01-05", "A", "MATERIAL DE CONSUMO", "LIMPEZA", 7],
    ])
    m = classificacao.marcar(df, arq_revisao=tmp_path / "nao_existe.csv")
    assert m["eh_juros_multa"].tolist() == [True, False, False, False]
    assert m["eh_dea"].tolist() == [False, False, True, False]


def test_revisao_manual_prevalece(tmp_path):
    rev = tmp_path / "rev.csv"
    rev.write_text("ElementoDespesa;SubelementoDespesa;incluir\nX;LIMPEZA;S\nX;MULTAS E JUROS POR ATRASO;N\n",
                   encoding="utf-8-sig")
    df = base([["2024-01-05", "A", "X", "MULTAS E JUROS POR ATRASO", 10],
               ["2024-01-05", "A", "X", "LIMPEZA", 7]])
    m = classificacao.marcar(df, arq_revisao=rev)
    assert m["eh_juros_multa"].tolist() == [False, True]


# ------------------------------------------------------------ indicadores
def test_serie_mensal_preenche_meses_vazios():
    s = ind.serie_mensal(base([["2024-03-10", "A", "", "", 100], ["2024-03-20", "A", "", "", 50]]), [2024])
    assert len(s) == 12 and s.sum() == 150 and s.loc["2024-03-01"] == 150 and s.loc["2024-01-01"] == 0


def test_ic_media_conhecido():
    ic = ind.ic_media(pd.Series([10, 12, 14]), 0.95)
    # média 12, dp 2, ep 2/sqrt(3), t(0.975, 2) = 4.3027
    assert ic.media == 12
    assert ic.inf == pytest.approx(12 - 4.3027 * 2 / np.sqrt(3), rel=1e-3)
    assert ind.ic_media(pd.Series([5])) is None


def test_ic_diferenca_sinal():
    ic = ind.ic_diferenca(pd.Series([10, 11, 9, 10] * 3), pd.Series([20, 21, 19, 20] * 3))
    assert ic.inf > 0


def test_alerta_dispara_so_no_pico():
    linhas = [[f"2024-{m:02d}-15", "A", "", "", 100 + (m % 3)] for m in range(1, 13)]
    linhas += [[f"2025-{m:02d}-15", "A", "", "", 100] for m in range(1, 13)]
    linhas.append(["2025-06-20", "A", "", "", 5000])
    al = ind.alertas_mensais(ind.serie_mensal(base(linhas), [2024, 2025]), 2025)
    assert al["alerta"].sum() == 1 and al.loc["2025-06-01", "alerta"]


def test_ranking_soma_bate_com_registros():
    df = base([["2024-01-01", "A", "", "", 10], ["2025-01-01", "A", "", "", 30],
               ["2025-02-01", "B", "", "", 5], ["2025-03-01", "A", "", "", 20]])
    r = ind.ranking_ugs(df, 2025).set_index("UnidadeGestora")
    assert r.loc["A", "Pago 2025"] == 50 and r.loc["A", "Registros"] == 2
    assert r.loc["A", "Variação %"] == pytest.approx(400)
    assert np.isnan(r.loc["B", "Variação %"])            # sem base no ano anterior
    assert r["Pago 2025"].sum() == df.loc[df.Ano == 2025, "ValorPago"].sum()



# ================================================ Pergunta 2: compras compartilhadas
def compras(linhas):
    return pd.DataFrame(linhas, columns=["Ano", "CodigoElementoDespesa", "ElementoDespesa", "SubelementoDespesa",
                                         "UnidadeGestora", "IdFavorecido", "TipoLicitacao", "ValorPago"])


def test_base_compras_filtra_universo():
    df = compras([
        [2024, "30", "MATERIAL", "MATERIAL DE LIMPEZA", "A", "1", "PREGÃO", 10],
        [2024, "11", "VENCIMENTOS", "SALÁRIO", "A", "2", "NÃO APLICÁVEL - DEMAIS CASOS", 999],    # folha
        [2024, "39", "SERVIÇOS PJ", "SERVIÇOS DE ENERGIA ELÉTRICA", "A", "3", "INEXIGÍVEL", 50],  # concessionária
        [2024, "30", "MATERIAL", "SUPRIMENTO DE FUNDOS - MATERIAL", "A", "4", "", 5],             # adiantamento
        [2024, "30", "MATERIAL", "MATERIAL DE LIMPEZA", "B", "5", "DISPENSA DE LICITAÇÃO", 0],    # valor zero
    ])
    b = ind.base_compras(df)
    assert b["ValorPago"].tolist() == [10]


def test_inexigibilidade_nao_conta_como_dispensa():
    df = compras([
        [2024, "30", "M", "X", "A", "1", "DISPENSA DE LICITAÇÃO", 10],
        [2024, "30", "M", "X", "B", "2", "INEXIGÍVEL", 10],
        [2024, "30", "M", "X", "C", "3", "INEXIGIBILIDADE DE LICITAÇÃO", 10],
        [2024, "30", "M", "X", "D", "4", "ADESÃO À ATA DE REGISTRO DE PREÇOS", 10],
    ])
    t = ind.indicadores_por_subelemento(ind.base_compras(df)).iloc[0]
    assert t["Pct_pag_dispensa"] == 25 and t["Pct_valor_ata"] == 25
    assert t["UGs"] == 4 and t["Fornecedores"] == 4


def test_score_ordena_e_respeita_min_ugs():
    linhas = []
    for i in range(6):   # FRAG: 6 UGs, 6 fornecedores, tickets pequenos, tudo por dispensa
        linhas.append([2024, "30", "M", "FRAG", f"U{i}", f"F{i}", "DISPENSA DE LICITAÇÃO", 100])
    for i in range(6):   # CENTRAL: 6 UGs, 1 fornecedor, tickets grandes, pregão
        linhas.append([2024, "30", "M", "CENTRAL", f"U{i}", "F0", "PREGÃO", 10_000])
    linhas.append([2024, "30", "M", "SO_UMA_UG", "U0", "F9", "DISPENSA DE LICITAÇÃO", 1])
    s = ind.score_oportunidade(ind.indicadores_por_subelemento(ind.base_compras(compras(linhas))), min_ugs=5)
    assert s["SubelementoDespesa"].tolist() == ["FRAG", "CENTRAL"]
    assert s["Score"].between(0, 100).all()


def test_ic_wilson_conhecido_e_limites():
    ic = ind.ic_wilson(50, 100, 0.95)
    assert ic.media == 50 and ic.inf == pytest.approx(40.38, abs=0.05) and ic.sup == pytest.approx(59.62, abs=0.05)
    zero = ind.ic_wilson(0, 20)
    assert zero.inf == 0 and zero.sup > 0          # não fica negativo nem colapsa em zero
    assert ind.ic_wilson(0, 0) is None


def test_ic_bootstrap_mediana_contem_mediana():
    ic = ind.ic_bootstrap_mediana(pd.Series(range(1, 101)))
    assert ic.inf <= ic.media <= ic.sup and ic.media == 50.5


def test_simular_economia():
    t = pd.DataFrame({"SubelementoDespesa": ["A", "B"], "Valor_pago": [1000.0, 500.0],
                      "Valor_dispensa": [200.0, 100.0]})
    assert ind.simular_economia(t, ["A"], 0.10, "dispensa") == (200.0, 20.0)
    assert ind.simular_economia(t, ["A", "B"], 0.10, "total") == (1500.0, 150.0)