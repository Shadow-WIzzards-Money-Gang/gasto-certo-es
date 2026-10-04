"""Gera a planilha de revisão manual dos subelementos de juros/multas.

Uso:  python -m src.revisar_categorias

Lista TODOS os subelementos que contêm JUROS/MULTA/MORA/ENCARGO (inclusive os que a
regra exclui, como juros da dívida), com total pago e nº de registros. A coluna
`incluir` vem com a sugestão automática (S/N): revisem linha a linha, salvem, e o app
passa a usar a revisão. Citem essa lista no relatório (auditoria do critério).
"""
from src import classificacao, etl

df = etl.carregar_processado()
texto = df["SubelementoDespesa"].fillna("") + " | " + df["ElementoDespesa"].fillna("")
candidatos = df[classificacao._contem(texto, classificacao.PALAVRAS_JUROS_MULTAS)].copy()
candidatos["sugestao"] = classificacao.sugerir_juros_multas(candidatos)

tabela = (
    candidatos.groupby(["ElementoDespesa", "SubelementoDespesa"])
    .agg(registros=("ValorPago", "size"), total_pago=("ValorPago", "sum"), sugestao=("sugestao", "first"))
    .reset_index().sort_values("total_pago", ascending=False)
)
tabela["incluir"] = tabela.pop("sugestao").map({True: "S", False: "N"})

arq = classificacao.ARQ_REVISAO
if arq.exists():
    raise SystemExit(f"{arq} já existe; apague-o se quiser gerar de novo.")
arq.parent.mkdir(parents=True, exist_ok=True)
tabela.to_csv(arq, sep=";", index=False, encoding="utf-8-sig", decimal=",")
print(tabela.to_string(index=False))
print(f"\nSalvo em {arq}. Revise a coluna 'incluir' (S/N) antes de usar.")
