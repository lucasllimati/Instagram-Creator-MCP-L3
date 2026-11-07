# Design: automação de conteúdo para @l3investir e @l3mktdigital

- **Data:** 2026-11-07
- **Estado:** aguardando revisão de Lucas
- **Origem:** `prompt-instagram-automacao.md` (a referência de conteúdo e marca continua valendo, exceto onde a seção 3 deste documento a corrige)

## 1. Objetivo e critérios de sucesso

Produzir e publicar conteúdo educativo em português do Brasil nos perfis `FIN` (@l3investir) e `MKT` (@l3mktdigital), chegando a 1 post por dia em cada perfil, com custo zero de infraestrutura e até 15 minutos por semana de revisão humana.

O projeto está pronto quando:

1. `/semana` gera a semana dos dois perfis e abre um PR com tabela e prévias das imagens.
2. Nenhum post que viole uma regra mensurável chega a `main` sem reprovação visível do CI, e `publicar.py` se recusa a publicá-lo.
3. Só publica o que está em `main`, e simular uma queda em qualquer etapa nunca gera post duplicado.
4. Erro de autorização ou bloqueio interrompe a conta afetada e abre uma issue, sem novas tentativas.
5. Um post real é publicado em cada conta com sucesso após a autorização de Lucas.

**Fora do escopo:** Reels, resposta a comentários e DMs, imagens geradas por IA, automação de curtidas ou follows.

## 2. Decisões tomadas

| Tema | Decisão |
|---|---|
| Autonomia | Aprovação semanal: fazer merge do PR é aprovar |
| Arquitetura | Subagentes do Claude Code e validadores Python; publicação no GitHub Actions, sem IA |
| Hospedagem | Repositório público `l3-media`, recebendo imagens só no momento de publicar; o repositório do projeto continua privado |
| Visual | Mantém a identidade dos avatares (seção 8) |
| Volume | Rampa: semana 1 com 3 posts por conta, semana 2 com 5, depois 7; stories a partir da semana 3 |

## 3. Correções ao prompt original

Conferido na documentação oficial da Meta em 2026-11-07.

| O prompt diz | Situação | Decisão |
|---|---|---|
| Stories com enquete, caixinha e link | A Meta informa: "Publishing stickers (i.e., link, poll, location) is not supported". Caixinha não é citada | Stories automáticos são só imagem; o texto convida a ver o post do dia. Enquete vira sugestão manual opcional no PR |
| Limite de 50–100 posts em 24h | A própria documentação traz 50 e 100 | Não assumir valor: ler `content_publishing_limit` a cada execução |
| Carrossel de até 10 itens | A documentação indica até 20 | Manter 10 como limite do projeto |
| GitHub raw do próprio repositório | O repositório é privado | Usar `l3-media` (público) |
| Editar `status` para `aprovado` | Mais trabalhoso e sujeito a erro | Merge do PR |
| Renovar o token mensalmente | Correto, mas faltava como gravar o novo valor | Token do GitHub restrito, com permissão de escrita em Secrets |
| *O Homem Mais Rico da Babilônia* em domínio público | Pela regra brasileira (autor + 70 anos) e a morte do autor em 1957, provavelmente só a partir de 2028. Traduções têm direitos próprios. Não verificado por fonte jurídica | Tratar como qualquer livro: só resumo autoral e citação curta creditada |

**Confirmado:** Business e Creator são contas aceitas; com Instagram Login não é necessária Página do Facebook; para contas próprias basta Standard Access, sem App Review; imagens só em JPEG, até 8 MB, proporção entre 4:5 e 1.91:1; o container expira em 24h; a checagem de status recomendada é uma vez por minuto, por até 5 minutos; o token dura 60 dias e só renova se tiver ao menos 24h e ainda estiver válido.

**Ainda não confirmado (testar na implementação):**
- Quais tipos de conta podem publicar stories, pois a documentação lida não diz.
- Se a API aceita alt text em imagens. Se aceitar, é enviado; se não, fica apenas registrado no `post.json`.

## 4. Arquitetura

```text
Rotina de domingo ou /semana manual (sessão orquestradora, branch semana/AAAA-WW)
  Analista -> Pesquisa -> Pauta -> Roteirista (1 por perfil)
    -> validar.py -> Revisor -> Legendas -> validar.py
    -> renderizar.py -> validar_imagem.py -> QA visual -> PR
                                                          |
                                       merge de Lucas = aprovação
                                                          |
GitHub Actions: publicar.yml -> validar -> copiar para l3-media -> API da Meta -> histórico
```

### Agentes

Ficam em `.claude/agents/`. Cada um recebe só os caminhos de que precisa e devolve JSON ou um arquivo.

| Agente | Modelo | Ferramentas | Saída |
|---|---|---|---|
| `analista` | Haiku | Read, Bash (script de insights), Write | `relatorios/semana-AAAA-WW.md` e sugestões |
| `pesquisador` | Sonnet | WebSearch, WebFetch, Write | `pesquisa/semana-AAAA-WW.md` (até 15 ideias por perfil, com fonte) |
| `pauteiro` | Sonnet | Read, Bash (`pautar.py`), Write | `calendario/semana-AAAA-WW.csv` |
| `roteirista` | Sonnet | Read, Write | `post.json` de cada post do perfil na semana |
| `revisor` | Sonnet | Read, Grep, Glob (sem escrita) | Veredito em JSON, gravado pelo orquestrador |
| `legendista` | Haiku | Read, Edit | Campos `legenda`, `hashtags` e `alt_text` |
| `qa-visual` | Sonnet | Read | Veredito em JSON por post |

O Revisor sem permissão de escrita garante a separação entre quem escreve e quem aprova. Se o Revisor reprovar, o post volta ao Roteirista por no máximo 2 ciclos e depois recebe `status=revisar_humano`, destacado no PR.

### Scripts

Ficam em `scripts/`, com lógica em módulos testáveis e sem depender de IA.

| Script | Função |
|---|---|
| `validar.py` | Regras de conteúdo (seção 6); usado no hook, no CI e no publicador |
| `validar_imagem.py` | Regras técnicas de imagem |
| `pautar.py` | Aplica a grade de pilares, a rampa e a repetição em 60 dias; gera `temas-60d.json` |
| `renderizar.py` | HTML para JPEG com Playwright; reprova texto que estoure a área do slide |
| `folha_contato.py` | Monta uma folha de miniaturas por post para o QA visual |
| `publicar.py` | Publica um perfil por execução; aceita `--dry-run` |
| `renovar_token.py` | Renova os tokens e atualiza o GitHub Secrets |
| `coletar_insights.py` | Busca os insights da semana e grava em `relatorios/dados/` |

### Estrutura do repositório

```text
CLAUDE.md                     # menos de 80 linhas: mapa e regras de ouro
.claude/
  settings.json               # permissões e hooks
  agents/                     # 7 subagentes
  skills/                     # semana, validar, status, post
  rules/                      # conteudo.md, fin.md, mkt.md, publicacao.md, visual.md
config/                       # rampa.yaml, limites.yaml, termos_proibidos.yaml, grade.yaml
marcas/                       # fin.yaml, mkt.yaml
schemas/                      # post.schema.json
templates/                    # capa, conteudo, cta, frase, story + fontes/
scripts/  tests/
pesquisa/  calendario/  relatorios/
fila/AAAA-MM-DD/{FIN,MKT}/    # post.json, estado.json, *.jpg
historico/
  publicacoes.csv  temas-60d.json  aprendizados.md  execucoes.jsonl
docs/
  referencia/prompt-instagram-automacao.md
  setup-meta.md
  operacao.md
.github/workflows/            # ci.yml, publicar.yml, renovar-token.yml, insights.yml
```

### Modelo de dados

**`post.json`** (validado por `schemas/post.schema.json`) segue o formato da seção "Agente 3" do prompt, acrescido de `legenda`, `hashtags[]`, `alt_text[]`, `tema_slug`, `citacao` (opcional), `status`. Valores de `status`: `roteiro`, `validado`, `revisado`, `renderizado`, `pronto`, `revisar_humano`.

Só posts com `status=pronto` em `main` podem ser publicados. O publicador nunca altera `post.json`.

**`estado.json`** é gravado apenas pelo publicador e guarda `container_ids`, `media_id`, `permalink`, horários e o estado de cada story. Estados: `pendente`, `container_criado`, `publicado`, `falhou`, `atrasado`.

## 5. Publicação e proteção contra bloqueio

Nada garante que uma conta nunca será bloqueada, pois a Meta não publica os critérios. A rampa é uma precaução do projeto, não uma regra da Meta.

### Agendamento

- `publicar.yml` roda em dois crons: FIN às 08:30 BRT (11:30 UTC) e MKT às 12:30 BRT (15:30 UTC). O GitHub pode atrasar crons, então a regra se baseia na data e não no minuto.
- A data de referência é a de `America/Sao_Paulo`. Um grupo de `concurrency` por perfil impede duas execuções simultâneas.
- A fila é o que está em `main`; a execução usa o commit mais recente.

### Sequência de `publicar.py <perfil>`

1. Para sem erro se a variável `PUBLICACAO_ATIVA` não for `true`.
2. Localiza o post do dia. Se não houver, encerra sem erro. Se houver post de dia anterior sem publicação, marca `atrasado` e abre uma issue, sem publicá-lo.
3. Lê `estado.json`. Se `publicado`, encerra. Se `container_criado`, consulta o container: `PUBLISHED` reconcilia o estado buscando o `media_id` na lista de mídia recente; `FINISHED` segue para o passo 8; `EXPIRED` ou `ERROR` marca `falhou` e abre uma issue, sem recriar sozinho.
4. Executa os validadores de novo.
5. Consulta `content_publishing_limit` e para se o uso estiver em 50% da cota ou mais.
6. Copia as imagens para `l3-media` e confirma que cada URL responde 200 com `image/jpeg`.
7. Cria os containers e **faz commit de `estado.json` antes de publicar**.
8. Aguarda `FINISHED` (uma consulta por minuto, até 5 minutos) e chama `media_publish`.
9. Grava `estado.json` e `historico/publicacoes.csv` e faz commit, com `pull --rebase` e nova tentativa em caso de conflito.
10. Publica os stories previstos pela rampa. A falha de um story é registrada e abre uma issue, sem desfazer o post.

### Tratamento de erros

| Tipo | Exemplos | Ação |
|---|---|---|
| Temporário | Timeout, HTTP 5xx | Até 3 tentativas com espera crescente, sem repetir `media_publish` antes de consultar o container |
| Cota | Limite atingido | Para e abre uma issue |
| Autorização ou bloqueio | Token inválido, permissão, ação bloqueada | **Para a conta sem nova tentativa** e abre uma issue com o código do erro |
| Conteúdo ou mídia | Imagem recusada | Marca `falhou` e abre uma issue |

### Tetos e regras

- **Teto:** 1 post e 4 stories por dia em cada conta, aplicado por `limites.yaml`.
- **Rampa:** `rampa.yaml` guarda a data de início e o volume por semana. Na semana 1 os dias são seg, qua e sex; na semana 2, seg a sex; depois, todos os dias.
- **Sem recuperação em lote:** um dia perdido nunca gera dois posts. Republicar exige um disparo manual com `--data`, que continua respeitando os demais passos.
- **Sem automação de interação:** o projeto não usa navegador, cookies, curtidas, follows, comentários nem DMs automáticos.
- **Sem conteúdo duplicado:** a legenda não pode repetir entre contas e o bloco de hashtags não pode ser igual ao do post anterior da mesma conta.

### Segredos

| Segredo | Uso |
|---|---|
| `IG_USER_ID_FIN`, `IG_USER_ID_MKT` | Identificam as contas |
| `IG_TOKEN_FIN`, `IG_TOKEN_MKT` | Publicação e renovação |
| `MEDIA_REPO_TOKEN` | Token do GitHub com escrita só em `l3-media` |
| `SECRETS_PAT` | Token do GitHub com escrita em Secrets só deste repositório, usado apenas em `renovar-token.yml` |

Tokens nunca aparecem em logs nem em mensagens de erro. A renovação roda a cada 30 dias e abre uma issue em caso de falha. As actions usadas ficam fixadas por SHA, e o CI inclui varredura de segredos.

O Claude não recebe os tokens: `.claude/settings.json` nega leitura de `.env*` e o comando `gh secret`, e as sessões usam apenas `--dry-run`.

## 6. Validadores

Reprovam sem usar IA e explicam o motivo com arquivo e slide. Os limites ficam em `config/`.

| Grupo | Regras |
|---|---|
| Estrutura | Respeita o schema; formato compatível com o pilar; carrossel dentro da faixa do pilar e no máximo 10 itens |
| Texto | Gancho até 10 palavras; título até 8; slide até 35; último slide com resumo e CTA |
| Legenda | Até 2.200 caracteres; primeira linha até 125; contém CTA |
| Hashtags | De 5 a 10; inclui `#l3investir` ou `#l3mktdigital`; sem termos da lista proibida; bloco diferente do post anterior |
| Acessibilidade | Um alt text por imagem |
| Promessas | Bloqueia "fique rico", "renda garantida", "10k seguidores" e variações |
| FIN | Bloqueia tickers (padrão como `PETR4`) e nomes de corretoras e produtos da lista; exige o aviso legal em posts de investimento; termos como Selic, IPCA, IR e FGC, ou percentuais, exigem fonte com data ou a marca `hipotetico: true` |
| MKT | Números de alcance ou engajamento exigem fonte; plataforma citada exige o ano |
| Livros | No máximo 1 citação, com menos de 15 palavras, autor e obra |
| Repetição | `tema_slug` não usado nos últimos 60 dias |
| Imagem | JPEG sRGB, sem MPO/JPS; 1080×1350 ou 1080×1920; até 8 MB; numeração correta |

Validadores por termo ou padrão não captam tudo. Julgamento de tom, clareza, originalidade e recomendação disfarçada cabe ao Revisor e, no fim, ao merge humano. Isto não substitui orientação jurídica sobre conteúdo financeiro.

## 7. Histórico, melhoria contínua e tokens

### Histórico

O repositório é a fonte da verdade, porque a rotina na nuvem não acessa a memória local desta máquina.

| Arquivo | Conteúdo | Escreve | Lê |
|---|---|---|---|
| `publicacoes.csv` | Registro completo e só acrescido | `publicar.py` | Scripts |
| `temas-60d.json` | Resumo de temas recentes | `pautar.py` | Pauteiro, validador |
| `aprendizados.md` | Até 30 linhas: aprendizado, evidência, data | Analista, por PR | Pauteiro, Roteirista |
| `execucoes.jsonl` | Etapas, reprovações, motivos, ciclos | Orquestrador | Analista |

**Melhoria contínua:** um mesmo motivo de reprovação em 3 ou mais posts de uma semana leva o Analista a sugerir um ajuste de regra no PR. Nenhum agente altera regras sem merge humano. A métrica principal é (salvamentos + compartilhamentos) / alcance, e as sugestões só citam dados medidos.

### Tokens

- `CLAUDE.md` com menos de 80 linhas; regras detalhadas lidas sob demanda.
- Prompt original fora do contexto automático.
- Um Roteirista por perfil para a semana, em vez de um agente por post.
- Validadores antes do Revisor; o Revisor recebe só o `post.json` e seu checklist.
- QA visual com folha de miniaturas, ampliando só o suspeito.
- Pesquisa limitada a 1 vez por semana, com até 15 ideias por perfil.
- `/semana` retoma pelo `status`, sem refazer o que está pronto.
- Pauteiro lê `temas-60d.json`, não o CSV completo.

### Skills do projeto

| Skill | Função |
|---|---|
| `/semana [AAAA-WW]` | Roda ou retoma a semana e abre o PR |
| `/validar [caminho]` | Roda os validadores |
| `/status` | Mostra a fila, as falhas e a próxima publicação |
| `/post <id>` | Refaz um único post |

As skills de `social-media-skills` (carrossel, gancho, legenda, hashtags, SEO, specs) são consultadas na implementação, levando o que servir para `.claude/rules/`. O projeto não depende delas em execução, pois a rotina na nuvem pode não tê-las.

### Hooks

Um hook `PostToolUse` em `.claude/settings.json` roda `validar.py` quando um `fila/**/post.json` é editado, devolvendo o erro na hora.

## 8. Identidade visual

| | FIN (@l3investir) | MKT (@l3mktdigital) |
|---|---|---|
| Principal | `#0F3D2E` verde-escuro | `#0A5CFF` azul-vivo, valor estimado a partir do avatar |
| Fundo alternativo | `#F7F5F0` off-white | `#111A3A` azul-noite |
| Apoio | `#3BB273` verde-claro | `#FFFFFF` branco |
| Destaque | `#E0B54A` dourado | `#FF7A2F` laranja |

Lucas pode informar o azul exato; basta trocar em `marcas/mkt.yaml`.

- **Fontes:** Montserrat ExtraBold nos títulos e Inter Regular no corpo, ambas com licença aberta e guardadas no repositório.
- **Tamanhos:** feed 1080×1350; stories 1080×1920.
- **Margens:** 80 px nas laterais; stories com 250 px livres em cima e embaixo.
- **Exportação:** JPEG sRGB, qualidade 90.
- **Conteúdo dos slides:** título, texto de apoio, numeração (`2/7`) e o @ do perfil no rodapé.
- **Proibido:** capas de livros, logos de terceiros, personagens protegidos, fotos de pessoas famosas.

Os templates usam formas e gráficos gerados pelo próprio sistema. Fotos de bancos gratuitos ficam fora da primeira versão.

### Bios sugeridas (troca manual)

- **FIN:** "Finanças sem economês: um conceito por dia para aplicar hoje. Conteúdo educativo, não é recomendação de investimento."
- **MKT:** "Marketing para pequenos negócios: o que dá para fazer hoje à tarde, sem agência."

## 9. Testes

| Camada | Cobre |
|---|---|
| Validadores | Por regra, ao menos um caso que passa e um que reprova |
| Publicador (HTTP simulado) | Queda entre container e publicação; `PUBLISHED`, `FINISHED`, `EXPIRED`, `ERROR`; 5xx com nova tentativa; token inválido sem nova tentativa; cota a 50%; post atrasado; pausa; execução repetida sem duplicar; token ausente nos logs |
| Pauta | Grade, rampa e repetição em 60 dias, com data fixa |
| Render | Dimensões, tamanho do arquivo, texto que estoura a área |
| Agentes | Validação do frontmatter e dos caminhos citados; o conteúdo gerado é avaliado pelos validadores |
| CI em todo PR | Testes, validação dos posts alterados e varredura de segredos |
| Dry-run | Tudo menos as chamadas que alteram algo na Meta |
| Teste real, com autorização | Um story em cada conta e depois um post, conferindo o `estado.json` |

Se o plano do GitHub não permitir proteção de branch em repositório privado, o CI apenas alerta, e a revalidação em `publicar.py` continua impedindo a publicação.

## 10. Riscos e limites conhecidos

| Risco | Resposta |
|---|---|
| Rotina na nuvem sem conseguir renderizar com Playwright | Testar cedo; plano B é rodar `/semana` manualmente no domingo, com a rotina como melhoria posterior |
| Meta falhar ao baixar imagens do GitHub raw | Testar no primeiro post real; plano B é o Cloudflare R2, trocando só a etapa de envio |
| Minutos do Actions em repositório privado | Estimativa de até 180 minutos por mês (2 execuções por dia, até 3 minutos cada); conferir a cota do plano |
| Crescimento do repositório com imagens | Estimativa de até 1,5 GB por ano; avaliar limpeza ao atingir 1 GB |
| Mudanças na API da Meta | Limites em `config/`; erros viram issue; rever a documentação a cada trimestre |
| Conteúdo financeiro incorreto apesar das checagens | Revisor, validadores, fontes com data e merge humano; a responsabilidade final é do aprovador |
| Rejeição do PR ou ausência de revisão | Sem merge, nada é publicado; é o comportamento seguro |

## 11. Ações exclusivas de Lucas

Guiadas por `docs/setup-meta.md`:

1. Confirmar que as duas contas são profissionais.
2. Criar o app na Meta e adicionar as duas contas, com `instagram_business_basic` e `instagram_business_content_publish`.
3. Gerar os tokens e cadastrar os segredos no GitHub.
4. Criar o repositório público `l3-media` e os tokens restritos do GitHub.
5. Trocar as bios.
6. Autorizar o teste real e definir a data de início da rampa.

## 12. Ordem de implementação

1. Base: `CLAUDE.md`, regras, configs, schema, validadores e testes.
2. Templates e renderização.
3. Publicador com HTTP simulado e `--dry-run`, mais os workflows.
4. Agentes, skills, hooks e histórico.
5. Primeira geração de semana com `/semana`, sem publicar, e teste de viabilidade da rotina na nuvem.
6. Configuração da Meta com Lucas, teste real e início da rampa.
