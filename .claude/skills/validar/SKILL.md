---
name: validar
description: Roda os validadores de conteúdo e imagem em um post ou em toda a fila.
argument-hint: "[caminho do post.json]"
---

Com caminho: `python scripts/validar.py <caminho>` e, se o post tiver imagens, `python scripts/validar_imagem.py <pasta>`.

Sem caminho: `python scripts/validar.py --todos`, que também confere as imagens de posts renderizados.

Mostre só as reprovações, agrupadas por post, e sugira a correção de cada uma. Não altere arquivos sem pedido.
