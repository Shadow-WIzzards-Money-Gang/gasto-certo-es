"""Classificação de subelementos de despesa (Pergunta 1: gasto evitável).

TODO (próxima etapa):
- listar_subelementos(df): valores distintos de ElementoDespesa / SubelementoDespesa
- marcar_juros_multas(df): flag `eh_juros_multa` por palavras-chave ("JUROS", "MULTA",
  "ENCARGO"), seguida de revisão manual da lista (publicada na tela de auditoria)
- marcar_dea(df): flag `eh_dea` para Despesas de Exercícios Anteriores (elemento 92)
- marcar_dispensa(df): flag `eh_dispensa` a partir de TipoLicitacao
"""

PALAVRAS_JUROS_MULTAS = ["JUROS", "MULTA", "ENCARGO"]
