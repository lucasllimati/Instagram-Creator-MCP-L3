---
paths:
  - "templates/**"
  - "marcas/**"
  - "scripts/renderizar.py"
---

# Visual

- **Consistência acima de novidade:** todo visual sai dos templates, com as cores de `marcas/`.
- **Tamanhos:** feed 1080×1350; stories 1080×1920, com 250 px livres em cima e embaixo. Margem lateral de 80 px.
- **Legibilidade no celular:** texto grande; o render reduz em até 30% se não couber e reprova se ainda assim estourar.
- **Contraste:** novas cores precisam passar em `tests/test_render.py`.
- **Elementos:** só formas e gráficos gerados pelo sistema.
- **Proibido:** capas de livros, logos de terceiros, personagens protegidos, fotos de pessoas famosas, texto embutido em imagem de IA.
