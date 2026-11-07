---
name: post
description: Refaz um único post da fila que ainda não foi publicado.
argument-hint: "<id> [o que mudar]"
disable-model-invocation: true
---

Refaça só o post indicado, na branch atual da semana. Se `estado.json` disser `publicado`, pare e avise.

1. Agente `roteirista`, com o caminho do post e o que mudar.
2. `python scripts/validar.py <post.json>`, agente `revisor` e agente `legendista`, se o texto mudou.
3. `python scripts/renderizar.py <pasta>`, `python scripts/validar_imagem.py <pasta>` e agente `qa-visual`.
4. `python scripts/status.py definir <pasta> pronto`.
