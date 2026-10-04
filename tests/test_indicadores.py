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
