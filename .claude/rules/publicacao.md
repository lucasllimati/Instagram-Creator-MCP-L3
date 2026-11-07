---
paths:
  - "scripts/publicar.py"
  - ".github/workflows/**"
  - "config/limites.yaml"
  - "config/rampa.yaml"
---

# Publicação e proteção contra bloqueio

Nada garante que uma conta nunca será bloqueada. Estas regras reduzem o risco e não devem ser enfraquecidas para ganhar volume.

- **Só API oficial.** Sem navegador, cookies ou automação de interação.
- **Rampa:** `config/rampa.yaml`. Não pule etapas.
- **Teto:** 1 post e 4 stories por dia em cada conta.
- **Cota:** consultada antes de publicar; para em 50%.
- **Sem recuperação em lote:** dia perdido vira `atrasado` e nunca gera dois posts.
- **Autorização ou bloqueio:** a conta entra em `historico/contas_pausadas.json`, sem novas tentativas. Só uma pessoa libera, depois de resolver a causa.
- **Sem duplicata:** container salvo antes de publicar; status consultado antes de repetir.
- **Testes:** toda mudança em `scripts/publicar.py` precisa de teste com a API simulada.
