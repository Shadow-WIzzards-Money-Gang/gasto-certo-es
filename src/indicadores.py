"""Indicadores das perguntas 1 e 2.

TODO (próxima etapa):
Pergunta 1 — gasto evitável
- serie_mensal_juros(df, orgao=None)
- ranking_orgaos_juros(df, ano)
- ic_media_mensal(serie, confianca=0.95)       # distribuição t
- alertas_mensais(df)                           # mês acima do IC do ano anterior

Pergunta 2 — compras compartilhadas
- indicadores_por_subelemento(df)               # nº UGs, fornecedores, pagamentos, ticket, % dispensa
- score_oportunidade(tabela)                    # min-max normalizado
- ic_bootstrap_mediana(valores, n=2000)
- ic_wilson(k, n)
- simular_economia(valor_pago, desconto)

Regra: empenhado, liquidado, pago e RAP nunca são somados entre si.
"""
