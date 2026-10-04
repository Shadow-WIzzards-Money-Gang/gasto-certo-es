"""ETL: lê os CSVs oficiais em data/raw, trata e salva o Parquet em data/processed.

Uso:
    python -m src.etl

Etapas
1. Lista os CSVs de data/raw.
2. Para cada arquivo: lê o cabeçalho, valida as colunas obrigatórias e carrega só
   as colunas usadas (tudo como texto, para não perder zeros à esquerda).
3. Converte valores monetários ("1.234,56" -> 1234.56) e datas.
4. Padroniza textos, mascara CPF e descarta colunas bancárias.
5. Junta os arquivos, remove duplicados por Id e salva Parquet + auditoria.

Cada decisão que altera o conjunto analisado é contada na auditoria.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd

from src import config

log = logging.getLogger("etl")


# ------------------------------------------------------------------ erros
class ErroImportacao(Exception):
    """Erro com mensagem amigável, exibível na interface."""


class SemArquivosError(ErroImportacao):
    pass


class EsquemaInvalidoError(ErroImportacao):
    def __init__(self, msg: str, auditoria: "AuditoriaArquivo | None" = None):
        super().__init__(msg)
        self.auditoria = auditoria


class DadosProcessadosAusentesError(ErroImportacao):
    pass


# --------------------------------------------------------------- auditoria
@dataclass
class AuditoriaArquivo:
    arquivo: str
    status: str = "ok"                # ok | rejeitado
    motivo: str = ""
    encoding: str = ""
    registros_lidos: int = 0
    valores_vazios: int = 0           # ValorPago vazio -> tratado como 0
    valores_invalidos: int = 0        # ValorPago não numérico -> registro excluído
    datas_invalidas: int = 0          # Data ilegível -> registro excluído
    registros_validos: int = 0
    colunas_faltando: list[str] = field(default_factory=list)


# ------------------------------------------------------- funções de limpeza
def converter_moeda(serie: pd.Series) -> pd.Series:
    """Converte texto monetário brasileiro em float.

    "1.234,56" -> 1234.56 | "-12,3" -> -12.3 | "R$ 10,00" -> 10.0
    Valores sem vírgula ("1234.56") são lidos como número com ponto decimal.
    Vazio -> NaN; não numérico -> NaN (quem chama diferencia os dois casos).
    """
    s = serie.astype("string").str.strip()
    s = s.str.replace(r"R\$|\s", "", regex=True)
    tem_virgula = s.str.contains(",", na=False)
    s = s.where(~tem_virgula, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce").astype("float64")


def converter_data(serie: pd.Series) -> pd.Series:
    """Converte datas ISO (2024-01-31, 2024-01-31T00:00:00) ou BR (31/01/2024)."""
    s = serie.astype("string").str.strip()
    iso = pd.to_datetime(s, format="ISO8601", errors="coerce")
    br = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    br_hora = pd.to_datetime(s, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    return iso.fillna(br).fillna(br_hora)


def padronizar_texto(serie: pd.Series) -> pd.Series:
    """Maiúsculas, sem espaços duplicados ou nas pontas; vazio vira NA."""
    s = serie.astype("string").str.strip().str.upper()
    s = s.str.replace(r"\s+", " ", regex=True)
    return s.replace("", pd.NA)


def mascarar_documento(serie: pd.Series) -> pd.Series:
    """Mascara CPF (11 dígitos): ***.456.789-**. CNPJ (14 dígitos) é público e mantido.

    Outros formatos (NIS, códigos genéricos) são totalmente ocultados.
    """
    def _mask(v):
        if pd.isna(v):
            return pd.NA
        dig = re.sub(r"\D", "", str(v))
        if len(dig) == 14:
            return f"{dig[:2]}.{dig[2:5]}.{dig[5:8]}/{dig[8:12]}-{dig[12:]}"
        if len(dig) == 11:
            return f"***.{dig[3:6]}.{dig[6:9]}-**"
        return "***"
    return serie.map(_mask).astype("string")


# ------------------------------------------------------------- leitura
def extrair_zips(dir_raw: Path, dir_interim: Path):
    extraidos, falhas = [], []
    for caminho_zip in sorted(p for p in dir_raw.iterdir() if p.suffix.lower() == ".zip"):
        try:
            with zipfile.ZipFile(caminho_zip) as zf:
                membros = [m for m in zf.infolist()
                           if not m.is_dir()
                           and m.filename.lower().endswith(".csv")
                           and not m.filename.startswith("__MACOSX")
                           and not Path(m.filename).name.startswith("._")]
                if not membros:
                    falhas.append(AuditoriaArquivo(arquivo=caminho_zip.name, status="rejeitado",
                                                   motivo="zip sem arquivos .csv"))
                    continue
                destino = dir_interim / caminho_zip.stem      # uma subpasta por zip
                destino.mkdir(parents=True, exist_ok=True)
                for m in membros:
                    alvo = destino / Path(m.filename).name     # só o nome: ignora "../"
                    if not alvo.exists() or alvo.stat().st_size != m.file_size:
                        with zf.open(m) as origem, open(alvo, "wb") as saida:
                            shutil.copyfileobj(origem, saida)
                    extraidos.append(alvo)
        except zipfile.BadZipFile:
            falhas.append(AuditoriaArquivo(arquivo=caminho_zip.name, status="rejeitado",
                                           motivo="arquivo .zip corrompido ou inválido"))
    return extraidos, falhas

def listar_arquivos(dir_raw: Path, dir_interim: Path):
    if not dir_raw.exists():
        raise SemArquivosError(f"Pasta {dir_raw} não existe.")
    soltos = sorted(p for p in dir_raw.iterdir() if p.suffix.lower() == ".csv")
    extraidos, falhas = extrair_zips(dir_raw, dir_interim)
    if not soltos and not extraidos and not falhas:
        raise SemArquivosError(f"Nenhum arquivo .zip ou .csv encontrado em {dir_raw}.")
    return soltos + extraidos, falhas


def nome_origem(caminho: Path, dir_interim: Path) -> str:
    if caminho.parent.parent == dir_interim:
        return f"{caminho.parent.name}.zip/{caminho.name}"
    return caminho.name

def _ler_cabecalho(caminho: Path) -> tuple[list[str], str]:
    for enc in (config.CSV_ENCODING, config.CSV_ENCODING_ALTERNATIVO):
        try:
            cols = pd.read_csv(caminho, sep=config.CSV_SEP, encoding=enc, nrows=0).columns
            return [c.strip() for c in cols], enc
        except UnicodeDecodeError:
            continue
    raise EsquemaInvalidoError(f"{caminho.name}: não foi possível decodificar o arquivo.")


def ler_csv(caminho: Path, nome: str) -> tuple[pd.DataFrame, AuditoriaArquivo]:
    """Lê um CSV oficial e devolve o DataFrame cru (texto) e sua auditoria inicial."""
    nome = nome or caminho.name
    aud = AuditoriaArquivo(arquivo=nome)
    colunas, enc = _ler_cabecalho(caminho)
    aud.encoding = enc
    if enc != config.CSV_ENCODING:
        log.warning("%s lido com encoding alternativo (%s).", caminho.name, enc)

    faltando = [c for c in config.COLUNAS_OBRIGATORIAS if c not in colunas]
    if faltando:
        aud.status, aud.colunas_faltando = "rejeitado", faltando
        aud.motivo = f"colunas obrigatórias ausentes: {', '.join(faltando)}"
        raise EsquemaInvalidoError(f"{nome}: {aud.motivo}", aud)

    usar = set(config.COLUNAS_USADAS)
    df = pd.read_csv(
        caminho, sep=config.CSV_SEP, encoding=enc, dtype=str,
        usecols=lambda c: c.strip() in usar, keep_default_na=False, na_values=[""],
        on_bad_lines="warn",
    )
    df.columns = [c.strip() for c in df.columns]
    df["arquivo_origem"] = nome
    aud.registros_lidos = len(df)
    return df, aud


# ------------------------------------------------------------- tratamento
def tratar(df: pd.DataFrame, aud: AuditoriaArquivo) -> pd.DataFrame:
    df = df.copy()

    # descarta qualquer coluna bancária (defensivo; não estão no dicionário)
    proibidas = [c for c in df.columns
                 if any(t in c.lower().replace(" ", "") for t in config.TERMOS_COLUNAS_PROIBIDAS)]
    df = df.drop(columns=proibidas)

    # valores monetários
    for col in config.COLUNAS_MOEDA:
        if col not in df.columns:
            continue
        bruto = df[col]
        convertido = converter_moeda(bruto)
        vazio = bruto.isna() | (bruto.astype("string").str.strip() == "")
        invalido = convertido.isna() & ~vazio
        if col == "ValorPago":
            aud.valores_vazios = int(vazio.sum())
            aud.valores_invalidos = int(invalido.sum())
        df[col] = convertido.mask(vazio, 0.0)  # vazio = nada pago naquele registro

    # remove registros com ValorPago ilegível
    df = df[df["ValorPago"].notna()]

    # datas
    df["Data"] = converter_data(df["Data"])
    aud.datas_invalidas = int(df["Data"].isna().sum())
    df = df[df["Data"].notna()]

    # ano: usa a coluna oficial; se faltar ou for inválida, deriva da data
    ano = pd.to_numeric(df["Ano"], errors="coerce") if "Ano" in df.columns else pd.Series(np.nan, index=df.index)
    df["Ano"] = ano.fillna(df["Data"].dt.year).astype("int64")
    df["Mes"] = df["Data"].dt.to_period("M").dt.to_timestamp()

    # textos
    for col in config.COLUNAS_TEXTO:
        if col in df.columns:
            df[col] = padronizar_texto(df[col])

    # privacidade
    if "CpfCnpjNis" in df.columns:
        df["CpfCnpjNis"] = mascarar_documento(df["CpfCnpjNis"])

    aud.registros_validos = len(df)
    return df


def remover_duplicados(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove duplicados por Id (quando existe); senão, linhas idênticas."""
    antes = len(df)
    if "Id" in df.columns and df["Id"].notna().any():
        com_id = df[df["Id"].notna()].drop_duplicates(subset="Id", keep="first")
        df = pd.concat([com_id, df[df["Id"].isna()]], ignore_index=True)
    else:
        df = df.drop_duplicates(subset=[c for c in df.columns if c != "arquivo_origem"])
    return df.reset_index(drop=True), antes - len(df)


# ------------------------------------------------------------- pipeline
def executar(dir_raw: Path = config.DIR_RAW, dir_processed: Path = config.DIR_PROCESSED, dir_interim=None) -> pd.DataFrame:
    """Roda o ETL completo. Arquivos inválidos são rejeitados sem parar os demais."""
    dir_interim = dir_interim or dir_raw.parent / "interim"
    arquivos, falhas_zip = listar_arquivos(dir_raw, dir_interim)
    partes, auditorias = [], list(falhas_zip)

    for caminho in arquivos:
        nome = nome_origem(caminho, dir_interim)
        log.info("Lendo %s", nome)
        try:
            bruto, aud = ler_csv(caminho, nome)
            partes.append(tratar(bruto, aud))
        except EsquemaInvalidoError as e:
            log.error(str(e))
            aud = e.auditoria or AuditoriaArquivo(arquivo=nome, status="rejeitado", motivo=str(e))
        auditorias.append(aud)

    if not partes:
        raise EsquemaInvalidoError("Nenhum arquivo válido em data/raw. Veja os motivos na auditoria.")

    df = pd.concat(partes, ignore_index=True)
    df, n_dup = remover_duplicados(df)

    tabela_aud = pd.DataFrame([asdict(a) for a in auditorias])
    tabela_aud["colunas_faltando"] = tabela_aud["colunas_faltando"].map(", ".join)
    tabela_aud.loc[len(tabela_aud)] = {
        "arquivo": "TOTAL (após remover duplicados)", "status": "",
        "motivo": f"{n_dup} duplicados removidos por Id", "encoding": "",
        "registros_lidos": tabela_aud["registros_lidos"].sum(),
        "valores_vazios": tabela_aud["valores_vazios"].sum(),
        "valores_invalidos": tabela_aud["valores_invalidos"].sum(),
        "datas_invalidas": tabela_aud["datas_invalidas"].sum(),
        "registros_validos": len(df), "colunas_faltando": "",
    }

    dir_processed.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dir_processed / config.ARQ_PARQUET.name, index=False)
    tabela_aud.to_csv(dir_processed / config.ARQ_AUDITORIA.name, index=False, sep=";", encoding="utf-8-sig")
    log.info("Salvo: %d registros válidos (%d duplicados removidos).", len(df), n_dup)
    return df


# ------------------------------------------------------- uso pela aplicação
def carregar_processado(dir_processed: Path = config.DIR_PROCESSED) -> pd.DataFrame:
    caminho = dir_processed / config.ARQ_PARQUET.name
    if not caminho.exists():
        raise DadosProcessadosAusentesError(
            "Dados tratados não encontrados. Rode `python -m src.etl` antes de abrir o app."
        )
    return pd.read_parquet(caminho)


def carregar_auditoria(dir_processed: Path = config.DIR_PROCESSED) -> pd.DataFrame:
    caminho = dir_processed / config.ARQ_AUDITORIA.name
    if not caminho.exists():
        raise DadosProcessadosAusentesError("Auditoria não encontrada. Rode `python -m src.etl`.")
    return pd.read_csv(caminho, sep=";", encoding="utf-8-sig")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    try:
        executar()
        print(carregar_auditoria().to_string(index=False))
    except ErroImportacao as e:
        log.error(str(e))
        raise SystemExit(1)
