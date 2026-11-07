---
name: evento
description: Cria o post de um evento econômico, como decisão do Copom, com gráfico de dados oficiais e PR próprio.
argument-hint: "copom [AAAA-MM-DD da reunião]"
disable-model-invocation: true
---

Crie o post de evento. Sem data, use hoje. **Não publique nada.** Leia `.claude/rules/atualidades.md`.

1. **Branch:** `evento/AAAA-MM-DD-copom` a partir de `main`.
2. **Dados:** `python scripts/dados_economicos.py --ate <dia seguinte à reunião>`. Se falhar, **pare e explique**; nunca use número de memória.
3. **Esqueleto:** `python scripts/evento.py copom --reuniao <data>`. Ele cria `fila/<dia seguinte>/FIN-evento/` com os números da série.
4. **Confirmação:** busque o comunicado oficial do Copom no site do Banco Central. Se o resultado divergir da série, pare e avise.
   - Se `fatos.json` trouxer `confirmar_no_comunicado: true` e o comunicado confirmar a manutenção, reescreva a capa e o slide 2 dizendo que o Copom manteve a taxa e adicione o comunicado às `fontes`. Se não for possível confirmar, deixe `revisar_humano`.
5. **Texto:** agente `roteirista` para preencher os campos `[preencher]`, sem alterar números. Depois, valide com `python scripts/validar.py`.
6. **Revisão:** agente `revisor`; se reprovar, um ciclo de correção.
7. **Legenda:** agente `legendista`.
8. **Imagens:** `python scripts/renderizar.py` e `python scripts/validar_imagem.py`, depois agente `qa-visual`.
9. **Pronto:** `python scripts/status.py definir <pasta> pronto` e `python scripts/validar.py --todos`.
10. **PR:** commit, push e PR. O título diz o prazo: "merge até 18:00 de hoje". Antes das 08:30 sai no horário normal; entre 08:30 e 18:00, às 18:00.

Sem merge até 18:00 do dia do post, nada é publicado naquela vaga. É o comportamento seguro.
