# Entrega pelo Telegram

Use este caminho enquanto a publicação automática não estiver disponível, por exemplo com a conta da Meta bloqueada. O projeto gera o conteúdo normalmente e, no horário de cada perfil, envia tudo a um canal seu. Você posta pelo celular.

Não precisa de conta na Meta. Calcule 10 minutos.

## O que chega no canal

Para cada post aprovado:

1. **Cabeçalho:** perfil, dia, formato, tema e horário sugerido.
2. **Imagens:** enviadas como arquivo, para o Telegram não comprimir, em 1080×1350 e na ordem certa.
3. **Vídeo para Reels:** só em carrossel, na vertical, com os slides e sem áudio. Escolha uma música da biblioteca do Instagram ao postar.
4. **Legenda:** mensagem só com a legenda e as hashtags. Toque e segure, copie e cole.
5. **Apoio:** alt text de cada imagem e a enquete sugerida, quando houver.
6. **Stories:** a partir da semana 3 da rampa, as imagens e os textos dos stories.

## 1. Criar o bot

1. No Telegram, abra o **@BotFather** e envie `/newbot`.
2. Escolha um nome (por exemplo, `L3 Conteúdo`) e um usuário terminado em `bot`.
3. Guarde o token que ele mostrar. **Não cole esse token em conversa com o Claude, em arquivos ou em commits.**

## 2. Criar o canal

1. Crie um canal **privado**, por exemplo `L3 Conteúdo`.
2. Em **Administradores**, adicione o bot com a permissão de publicar mensagens.
3. Envie qualquer mensagem no canal.
4. Para descobrir o ID do canal, abra no navegador `https://api.telegram.org/bot<TOKEN>/getUpdates` e procure `"chat":{"id":-100...`. O ID começa com `-100`.

Se a resposta vier vazia, envie outra mensagem no canal e recarregue a página.

## 3. Cadastrar no GitHub

Cole o valor quando cada comando pedir:

```bash
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
gh variable set ENTREGA_TELEGRAM --body true
```

## 4. Testar

Com um post aprovado em `main` para hoje, abra **Actions > Entregar no Telegram > Run workflow** e escolha o perfil. O post deve chegar ao canal em alguns minutos.

Também dá para testar do seu computador, com as variáveis definidas só no seu terminal:

```powershell
$env:TELEGRAM_BOT_TOKEN = "<token>"; $env:TELEGRAM_CHAT_ID = "<id>"
python scripts/entregar_telegram.py FIN --confirmar-local
```

Fora do GitHub Actions, o estado fica salvo só no seu disco.

## Cuidados

- **Conta restrita:** se a restrição estiver nas contas do Instagram, poste com calma e siga a rampa de `config/rampa.yaml`. Postar à mão não elimina esse risco.
- **Sem duplicata:** cada post é entregue uma vez. Se o envio parar no meio, a próxima execução continua de onde parou.
- **Tema usado:** post entregue conta como usado e não se repete por 60 dias, mesmo que você não poste.
- **Pausar:** `gh variable set ENTREGA_TELEGRAM --body false`.
- **Publicação automática:** deixe `PUBLICACAO_ATIVA=false` enquanto usar o Telegram, para o mesmo post não sair duas vezes.
