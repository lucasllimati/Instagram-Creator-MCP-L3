---
paths:
  - "fila/*/FIN*/**"
  - "exemplos/FIN/**"
---

# Regras de FIN (@l3investir)

**Conteúdo educativo.** Explica conceitos, compara categorias e mostra contas.

## Nunca

- Recomendar ativo, ação, fundo, cripto, banco ou corretora para compra ou venda.
- Dizer o que a pessoa deve fazer com o dinheiro dela em um produto específico. Prefira "o que observar" a "o que comprar".
- Prever juros, inflação, câmbio ou preço de ativo por conta própria. Só relate previsões oficiais, com fonte.
- Usar urgência, medo ou ganância.

O validador pega tickers e nomes conhecidos, mas não pega recomendação disfarçada. Essa checagem é do Revisor.

## Números

- Selic, IPCA, IR, FGC e outros dados oficiais exigem fonte e data, ou `hipotetico: true`.
- Exemplos usam valores redondos em reais e deixam claro: "supondo juros de 1% ao mês".
- Para séries em `dados/`, use `dados_ref`; o validador compara o texto com a série.

## Aviso legal

Em posts sobre investimento, a legenda traz o texto exato de `aviso_legal` em `marcas/fin.yaml`.
