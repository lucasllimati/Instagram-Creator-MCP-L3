# Operação

## Rotina

| Quando | Quem | O quê |
|---|---|---|
| Diário, 07:00 | Actions | Radar de notícias e dados econômicos |
| Domingo, 06:00 | Actions | Coleta de insights |
| Domingo | Claude | `/semana`, que abre o PR |
| Domingo, 10 a 15 min | Você | Revisa o PR e faz o merge |
| Diário, 08:30 e 12:30 | Actions | Publica FIN e MKT pela API |
| De hora em hora, 08:17 a 23:17 | Actions | Entrega no Telegram o que já passou do horário do perfil |
| Diário, 18:00 | Actions | FIN: só post de evento |

## Post sob demanda (`/hoje`)

Para rodar o fluxo completo agora, no Claude Code:

1. `/hoje` faz os dois perfis; `/hoje FIN` ou `/hoje MKT`, só um.
2. O Claude busca notícias, escolhe o tema, escreve, revisa, gera as imagens e abre o PR.
3. Você confere a prévia e faz o merge.
4. O workflow "Entregar no Telegram" roda no merge e entrega, em poucos minutos, todo post com a data de hoje.

Posts de outros dias, como os da `/semana`, continuam esperando o horário agendado.

## Modo de entrega

Ative um modo por vez, para o mesmo post não sair duas vezes.

| Modo | Variável | Guia |
|---|---|---|
| Publicação automática pela API | `PUBLICACAO_ATIVA=true` | `docs/setup-meta.md` |
| Entrega no Telegram para postar à mão | `ENTREGA_TELEGRAM=true` | `docs/setup-telegram.md` |
| Dia 1 de cada mês | Actions | Renova os tokens |

## Revisar o PR da semana

1. Abra as prévias da tabela.
2. Para vetar um post, apague a pasta dele na branch.
3. Veja a seção "Precisa de olhar humano". Esses posts não saem até ficarem com status `pronto`.
4. Com o CI verde, faça o merge.

Sem merge, nada é publicado.

## Decisão do Copom

1. Confira as datas em `config/calendario_economico.yaml`. Preencha o ano seguinte e marque `confirmado: true` a partir do site do Banco Central.
2. A Pauta reserva a vaga de FIN no dia seguinte à reunião.
3. Na noite da decisão ou na manhã seguinte, rode `/evento copom`.
4. Faça o merge do PR até 18:00 do dia do post.

## Branches

- **No GitHub:** a opção "Automatically delete head branches" está ligada, e a branch some no merge do PR.
- **No computador:** `git config fetch.prune true` tira as referências remotas apagadas. Os comandos `/hoje`, `/semana`, `/evento` e `/noticia` apagam as branches locais já incorporadas ao começar.
- **À mão:** `git checkout main && git pull && git branch --merged main` lista o que pode sair; apague com `git branch -d <nome>`. O `-d` recusa branch com trabalho ainda não incorporado.

## Pausar tudo

```bash
gh variable set PUBLICACAO_ATIVA --body false
```

## Incidentes

As falhas abrem issues no GitHub. Rode `/status` para um resumo.

### "Conta pausada: autorização ou bloqueio"

A publicação da conta parou sem novas tentativas. **Não force.**

1. Abra o app do Instagram na conta e veja se há aviso ou restrição.
2. Veja o código de erro na issue. Token: gere outro e atualize com `gh secret set IG_TOKEN_FIN`.
3. Se for restrição da conta, resolva pelo app e espere antes de voltar.
4. Remova a entrada do perfil em `historico/contas_pausadas.json` e faça commit em `main`.

### "Post atrasado"

O workflow não publicou no dia. Para publicar mesmo assim, use **Actions > Publicar > Run workflow**, com `dry_run` desligado e a data do post. Se o tema perdeu a validade, não faça nada.

### "Cota de publicação"

O uso passou de 50% da cota da Meta, o que não é esperado neste volume. Veja se há outra ferramenta publicando nessa conta.

### "Falha ao salvar o estado"

O GitHub não aceitou o commit, e o post não foi publicado. Republique manualmente quando o GitHub voltar.

### "Falha ao renovar tokens"

Rode **Actions > Renovar tokens** de novo. Se o token já expirou, gere outro no painel da Meta. Confira também a validade do `SECRETS_PAT`.

### "Falha ao enviar ... ao Telegram"

A issue lista as partes já enviadas, e a próxima execução continua de onde parou. Para não esperar o dia seguinte, rode **Actions > Entregar no Telegram** com a data do post. Erro `HTTP 401` indica token do bot errado; erro `HTTP 400` com "chat not found" indica ID do canal errado ou bot sem permissão de administrador.

### Container `falhou`

Abra a issue. Se for imagem recusada pela Meta, teste a URL pública e veja `docs/setup-meta.md`.

## Testar localmente

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
python scripts/publicar.py FIN --dry-run
```

## Manutenção

- **A cada trimestre:** revise a versão da API e os limites em `config/limites.yaml`, e as fontes em `config/fontes.yaml`.
- **Se o repositório passar de 1 GB:** avalie apagar imagens antigas de `fila/`.
- **Tokens do GitHub:** troque antes da validade.
