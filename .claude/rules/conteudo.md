---
paths:
  - "fila/**"
  - "calendario/**"
  - "exemplos/**"
---

# Regras de conteúdo

Os limites numéricos ficam em `config/limites.yaml` e são verificados por `scripts/validar.py`. Aqui está o que exige julgamento.

## Objetivo

Educar com conteúdo que as pessoas salvam e compartilham. Essa é a métrica principal, não curtidas.

## Carrossel

- **Um post, uma ideia.** Se precisar de duas, vira dois posts.
- **A capa decide tudo:** gancho (pergunta, número, contradição ou promessa concreta) e o que a pessoa ganha ao arrastar.
- **Uma ideia por slide.** Cada slide faz a pessoa querer o próximo. Se precisa de um parágrafo, são dois slides.
- **Sem enchimento:** um carrossel enxuto vence um longo. Use o menor número de slides da faixa do pilar que entregue a ideia.
- **Último slide:** resumo em uma frase e um único CTA, de preferência salvar.

## Legenda

- A primeira linha repete o gancho de outra forma, com a palavra-chave nos primeiros 80 caracteres. O Instagram indexa a legenda na busca.
- O corpo complementa os slides em 3 a 6 linhas curtas, sem repetir.
- Inclua um CTA claro. Em FIN, inclua o aviso legal de `marcas/fin.yaml` em posts sobre investimento.

## Hashtags

- Exatamente 5: 1 ou 2 amplas do nicho, 2 ou 3 específicas do tema e a de marca.
- Prefira tags de nicho às genéricas. Varie o bloco conforme o tema.
- Hashtag ajuda a categorizar; palavra-chave na legenda ajuda mais na busca.

## Alt text

Descreva o que a imagem comunica, incluindo o texto principal. Um por imagem, na ordem: slides e depois stories. Gráfico: diga a tendência e o valor final.

## Stories

Só imagem e texto; a API não publica enquete, caixinha nem link. Se valer a pena, sugira uma enquete no campo `enquete_manual`, que aparece no PR para postagem manual.

## Originalidade e livros

- Nunca copie texto de outros perfis, sites ou livros. Escreva com palavras próprias.
- Livro: resumo autoral com título e autor em `livro`. No máximo 1 citação, com menos de 15 palavras, entre aspas, com autor e obra.
- Trate todo livro assim, inclusive *O Homem Mais Rico da Babilônia*.
- Proibido: transcrever trechos e usar capas ou ilustrações.

## Linguagem

Português do Brasil, claro e direto. Explique todo jargão. Sem sensacionalismo nem promessa de resultado.
