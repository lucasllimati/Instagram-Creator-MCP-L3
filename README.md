# Instagram L3

Produção de conteúdo educativo para [@l3investir](https://www.instagram.com/l3investir/) e [@l3mktdigital](https://www.instagram.com/l3mktdigital/), com aprovação humana e publicação pela API oficial do Instagram.

Agentes do Claude Code geram a semana e abrem um Pull Request. O merge aprova. O GitHub Actions publica um post por dia em cada conta.

## Começar

1. Configure contas, tokens e segredos com [docs/setup-meta.md](docs/setup-meta.md).
2. Instale as dependências:

   ```bash
   pip install -r requirements-dev.txt
   python -m playwright install chromium
   python -m pytest
   ```

3. No Claude Code, rode `/semana`.

A rotina e os incidentes estão em [docs/operacao.md](docs/operacao.md), e o design completo em [docs/superpowers/specs/](docs/superpowers/specs/2026-11-07-instagram-l3-automacao-design.md).
