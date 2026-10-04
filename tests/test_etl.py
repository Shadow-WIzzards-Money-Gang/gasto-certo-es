import pandas as pd
import pytest

from src import etl

CABECALHO = "Id;Ano;Data;ValorEmpenho;ValorLiquidado;ValorPago;ValorRap;Orgao;UnidadeGestora;ElementoDespesa;SubelementoDespesa;CpfCnpjNis;TipoLicitacao"


def escrever_csv(caminho, linhas, cabecalho=CABECALHO):
    # UTF-8 com BOM, como os arquivos oficiais
    caminho.write_text("\n".join([cabecalho, *linhas]), encoding="utf-8-sig")


@pytest.fixture
def pastas(tmp_path):
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir()
    return raw, proc


# ------------------------------------------------------- funções unitárias
def test_converter_moeda():
    s = pd.Series(["1.234,56", "-12,3", "R$ 10,00", "1234.56", "abc", None, "0,00"])
    r = etl.converter_moeda(s)
    assert r.iloc[0] == pytest.approx(1234.56)
    assert r.iloc[1] == pytest.approx(-12.3)
    assert r.iloc[2] == pytest.approx(10.0)
    assert r.iloc[3] == pytest.approx(1234.56)
    assert pd.isna(r.iloc[4]) and pd.isna(r.iloc[5])
    assert r.iloc[6] == 0


def test_converter_data_formatos():
    r = etl.converter_data(pd.Series(["2024-01-31", "2024-02-01T00:00:00", "15/03/2025", "xx"]))
    assert r.iloc[0] == pd.Timestamp("2024-01-31")
    assert r.iloc[1] == pd.Timestamp("2024-02-01")
    assert r.iloc[2] == pd.Timestamp("2025-03-15")
    assert pd.isna(r.iloc[3])


def test_mascarar_documento():
    r = etl.mascarar_documento(pd.Series(["123.456.789-01", "12345678000199", "999"]))
    assert r.iloc[0] == "***.456.789-**"
    assert r.iloc[1] == "12.345.678/0001-99"
    assert r.iloc[2] == "***"


def test_padronizar_texto():
    r = etl.padronizar_texto(pd.Series(["  secretaria   de saude ", ""]))
    assert r.iloc[0] == "SECRETARIA DE SAUDE"
    assert pd.isna(r.iloc[1])


# ------------------------------------------------------------- pipeline
def test_pipeline_completo(pastas):
    raw, proc = pastas
    escrever_csv(raw / "despesas_2024.csv", [
        "1;2024;2024-01-10;100,00;100,00;1.000,50;0,00;Sesa;UG1;Juros;Juros de mora;12345678901;Dispensa",
        "2;2024;10/02/2024;0;0;;0;Sesa;UG1;Material;Limpeza;12345678000199;Pregão",   # ValorPago vazio -> 0
        "3;2024;data-ruim;0;0;5,00;0;Sesa;UG1;Material;Limpeza;;",                      # data inválida
        "4;2024;2024-03-01;0;0;abc;0;Sesa;UG1;Material;Limpeza;;",                      # valor inválido
    ])
    escrever_csv(raw / "despesas_2025.csv", [
        "1;2024;2024-01-10;100,00;100,00;1.000,50;0,00;Sesa;UG1;Juros;Juros de mora;;Dispensa",  # duplicado
        "5;2025;2025-05-05;0;0;20,00;3,00;Sedu;UG2;Material;Limpeza;;Dispensa",
    ])

    df = etl.executar(raw, proc)

    assert sorted(df["Id"]) == ["1", "2", "5"]
    assert df.loc[df["Id"] == "1", "ValorPago"].item() == pytest.approx(1000.50)
    assert df.loc[df["Id"] == "2", "ValorPago"].item() == 0
    assert df.loc[df["Id"] == "1", "CpfCnpjNis"].item() == "***.456.789-**"
    assert set(df["Orgao"]) == {"SESA", "SEDU"}
    assert (proc / "despesas.parquet").exists()

    aud = etl.carregar_auditoria(proc)
    a24 = aud[aud["arquivo"] == "despesas_2024.csv"].iloc[0]
    assert a24["registros_lidos"] == 4
    assert a24["valores_vazios"] == 1
    assert a24["valores_invalidos"] == 1
    assert a24["datas_invalidas"] == 1
    assert a24["registros_validos"] == 2
    assert aud.iloc[-1]["registros_validos"] == 3   # total após duplicados


def test_soma_preservada(pastas):
    """A soma no Parquet deve bater com a soma dos registros válidos de origem."""
    raw, proc = pastas
    escrever_csv(raw / "a.csv", [
        f"{i};2024;2024-01-01;0;0;{i},50;0;O;U;E;S;;" for i in range(1, 51)
    ])
    df = etl.executar(raw, proc)
    assert df["ValorPago"].sum() == pytest.approx(sum(i + 0.5 for i in range(1, 51)))


def test_arquivo_sem_coluna_obrigatoria_e_rejeitado(pastas):
    raw, proc = pastas
    escrever_csv(raw / "bom.csv", ["1;2024;2024-01-01;0;0;1,00;0;O;U;E;S;;"])
    escrever_csv(raw / "ruim.csv", ["1;2024"], cabecalho="Id;Ano")
    df = etl.executar(raw, proc)
    assert len(df) == 1
    aud = etl.carregar_auditoria(proc)
    assert aud.loc[aud["arquivo"] == "ruim.csv", "status"].item() == "rejeitado"


def test_todos_invalidos_gera_erro(pastas):
    raw, proc = pastas
    escrever_csv(raw / "ruim.csv", ["1;2024"], cabecalho="Id;Ano")
    with pytest.raises(etl.EsquemaInvalidoError):
        etl.executar(raw, proc)


def test_pasta_vazia_gera_erro(pastas):
    raw, proc = pastas
    with pytest.raises(etl.SemArquivosError):
        etl.executar(raw, proc)


def test_carregar_sem_processar_gera_erro(tmp_path):
    with pytest.raises(etl.DadosProcessadosAusentesError):
        etl.carregar_processado(tmp_path)
