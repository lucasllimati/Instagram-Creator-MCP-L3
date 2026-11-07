---
name: semana
description: Gera ou retoma o conteúdo de uma semana dos dois perfis e abre o PR de aprovação.
argument-hint: "[AAAA-WW]"
disable-model-invocation: true
---

Orquestre a semana indicada. Sem argumento, use a próxima semana ISO. **Não publique nada.**

Antes de cada etapa, veja o que já existe e pule o que estiver pronto. Passe caminhos aos agentes, não conteúdo colado.

1. **Branch:** `semana/AAAA-WW` a partir de `main`; se existir, continue nela.
2. **Dados:** `python scripts/pautar.py temas` e `python scripts/dados_economicos.py`. Se os dados falharem, siga sem eles e registre.
3. **Analista:** agente `analista`, se houver dados em `relatorios/dados/` e o relatório da semana não existir.
4. **Pesquisa:** agente `pesquisador`, se `pesquisa/semana-AAAA-WW.md` não existir.
5. **Pauta:** `python scripts/pautar.py gerar AAAA-WW`; depois o agente `pauteiro`.
6. **Roteiro:** um agente `roteirista` para FIN e outro para MKT, em paralelo.
7. **Validação:** `python scripts/validar.py` nos arquivos. Corrija reprovações pelo Roteirista. Marque aprovados com `python scripts/status.py definir <pasta> validado`.
8. **Revisão:** agente `revisor` com os posts validados.
   - `aprovado`: marque `revisado`.
   - `revisar`: devolva ao Roteirista e repita os passos 7 e 8, até 2 ciclos. Depois, marque `revisar_humano` e siga.
9. **Legendas:** agente `legendista` nos posts `revisado`. Se o validador apontar erro de legenda, devolva ao agente.
10. **Imagens:** `python scripts/renderizar.py <pastas>` e `python scripts/validar_imagem.py <pastas>`. Texto estourado volta ao Roteirista. Marque `renderizado`.
11. **QA visual:** agente `qa-visual`. Se `ajustar`, corrija, renderize de novo e repita uma vez. Se persistir, marque `revisar_humano`.
12. **Pronto:** marque `pronto` os posts aprovados. Rode `python scripts/validar.py --todos`.
13. **Histórico:** `python scripts/pautar.py temas` e `python scripts/status.py registrar '<json>'`, com semana, posts, reprovações e motivos, ciclos e itens para humano.
14. **PR:** faça commit, envie a branch e abra o PR com o corpo gerado por `python scripts/status.py pr AAAA-WW semana/AAAA-WW <dono/repo>`.

Ao final, informe: tabela `data | perfil | pilar | formato | gancho | status`, itens para olhar humano com o motivo, fontes usadas e recomendações do Analista.
