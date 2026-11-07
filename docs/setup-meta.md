# Configuração inicial

Estes passos só você pode fazer, porque envolvem suas contas e credenciais. Calcule cerca de 1 hora. As telas da Meta mudam com frequência, então os nomes podem variar um pouco.

**Nunca cole tokens em conversa com o Claude, em arquivos ou em commits.** Eles vão só para GitHub Secrets.

## 1. Conferir as contas

No app do Instagram, em @l3investir e @l3mktdigital: **Configurações > Tipo de conta e ferramentas**. As duas precisam ser profissionais (Empresa ou Criador de conteúdo).

## 2. Trocar as bios

Sugestões alinhadas às regras do projeto:

- **@l3investir:** Finanças sem economês: um conceito por dia para aplicar hoje. Conteúdo educativo, não é recomendação de investimento.
- **@l3mktdigital:** Marketing para pequenos negócios: o que dá para fazer hoje à tarde, sem agência.

## 3. Criar o app na Meta

1. Em <https://developers.facebook.com/apps>, crie um app do tipo **Business**.
2. Adicione o produto **Instagram** e escolha **API setup with Instagram login**.
3. Adicione as duas contas como testadoras do Instagram e aceite o convite em cada uma.
4. Confirme as permissões: `instagram_business_basic`, `instagram_business_content_publish` e `instagram_business_manage_insights`.

Para contas suas, o Standard Access basta, sem App Review, segundo a documentação da Meta.

## 4. Gerar os tokens

No painel do app, gere um **token de longa duração** para cada conta e anote o **ID do usuário do Instagram**. Esse token dura 60 dias, e o projeto renova todo mês.

## 5. Criar o repositório de mídia

```bash
gh repo create l3-media --public --description "Imagens publicadas por @l3investir e @l3mktdigital"
```

Faça um commit inicial nele (um README basta), para a branch `main` existir. Tudo o que entrar nele fica público.

## 6. Criar os tokens do GitHub

Em **Settings > Developer settings > Fine-grained tokens**, crie dois, com validade de até 1 ano e anote a data de troca:

| Nome | Repositório | Permissão |
|---|---|---|
| `MEDIA_REPO_TOKEN` | só `l3-media` | Contents: Read and write |
| `SECRETS_PAT` | só `Instagram-Creator-MCP-L3` | Secrets: Read and write |

## 7. Cadastrar segredos e variável

Rode cada comando e cole o valor quando for pedido, para que ele não fique no histórico do terminal:

```bash
gh secret set IG_USER_ID_FIN
gh secret set IG_USER_ID_MKT
gh secret set IG_TOKEN_FIN
gh secret set IG_TOKEN_MKT
gh secret set MEDIA_REPO_TOKEN
gh secret set SECRETS_PAT
gh variable set PUBLICACAO_ATIVA --body false
```

Mantenha `PUBLICACAO_ATIVA=false` até concluir o teste real.

## 8. Definir o início da rampa

Em `config/rampa.yaml`, coloque em `inicio` a segunda-feira da primeira semana, no formato `AAAA-MM-DD`.

## 9. Testar antes de publicar

1. Em **Actions > Publicar > Run workflow**, rode com `dry_run` ligado para cada perfil.
2. Com um post real na fila, ligue a publicação: `gh variable set PUBLICACAO_ATIVA --body true`.
3. Primeiro, publique um story real em cada conta. Ele some em 24 horas e confirma que a conta pode publicar stories pela API.
4. Depois, publique um post em cada conta e confira a imagem, a legenda e `estado.json`.

O teste real também confirma dois pontos que só a API responde: o envio do token no cabeçalho e o download das imagens pelo GitHub raw. Se a Meta recusar as imagens, o plano B é o Cloudflare R2.
