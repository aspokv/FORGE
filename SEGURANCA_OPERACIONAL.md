# Segurança operacional do FORGE

Duas coisas que **eu não faço por você**, porque exigem acesso a painéis que não tenho e
porque revogar credencial de produção sem combinar derruba o sistema no ar: a conferência
do MongoDB Atlas e a rotação de chaves.

Este documento é o roteiro exato. Nenhum valor de segredo aparece aqui — só nomes.

---

## 1. MongoDB Atlas: conferir se existe `0.0.0.0/0`

Produção usa Atlas. O `docker-compose.yml` mantém o serviço `mongo` comentado de
propósito: o banco não sobe na VPS.

### Como conferir (2 minutos)

1. Entre em <https://cloud.mongodb.com> e escolha o projeto do FORGE.
2. Menu lateral → **Security** → **Network Access**.
3. Olhe a coluna **IP Address** da lista **IP Access List**.

**O que você está procurando:** uma linha com `0.0.0.0/0`. O Atlas costuma rotulá-la como
`ACCESS FROM ANYWHERE`.

| O que aparece | Significa | Risco |
|---|---|---|
| `0.0.0.0/0` | qualquer IP da internet pode tentar conectar | **ALTO** |
| IP único da VPS (`/32`) | só o servidor do FORGE conecta | correto |
| Faixa ampla (ex.: `/16`, `/8`) | o vizinho do datacenter também alcança | MÉDIO |

O `0.0.0.0/0` **não** significa acesso livre aos dados: a autenticação continua exigindo
usuário e senha. O que ele faz é expor a porta do banco ao mundo, transformando qualquer
vazamento de senha, qualquer falha do próprio Atlas e qualquer tentativa de força bruta em
algo que pode ser explorado de qualquer lugar, em vez de só de dentro da sua rede.

### Quais IPs realmente precisam de acesso

**Apenas um: o IP público de saída da VPS do Coolify.**

O backend é o único que fala com o Mongo. Ele roda em container, sem porta publicada
(`expose`, não `ports`), e sai para a internet pelo IP da VPS.

Para descobrir esse IP, no terminal da VPS:

```
curl -s https://ifconfig.me
```

Se você usa Atlas gratuito (M0), a lista de IPs é limitada — mas um `/32` cabe.

### Se você mexer em produção pelo seu computador

Ferramenta local (Compass, mongosh) precisa do **seu** IP também. Duas opções, em ordem
de preferência:

1. adicione seu IP temporariamente e **remova quando terminar** — o Atlas oferece
   "Add Current IP Address" com expiração de 6 horas;
2. use o acesso de dentro da VPS, por SSH, e não adicione IP nenhum.

Nunca deixe seu IP residencial permanente na lista: ele muda, e o registro antigo passa a
liberar um endereço que hoje é de outra pessoa.

### Usuário do banco com o menor privilégio

Ainda em **Security** → **Database Access**, confira o usuário que o backend usa.

| Papel | Serve? |
|---|---|
| `atlasAdmin` | **não** — pode apagar clusters inteiros |
| `readWriteAnyDatabase` | **não** — alcança bancos que não são do FORGE |
| `readWrite` **restrito ao banco do FORGE** | **sim, é este** |

O nome do banco é o valor de `DB_NAME` no Coolify. O backend só faz leitura e escrita de
documentos: não cria índice fora do startup, não administra o cluster, não lê outro banco.

Se hoje o papel for mais amplo, o caminho seguro é: criar um usuário novo com
`readWrite` no banco certo, trocar `MONGO_URL` no Coolify, redeploy, confirmar que o app
subiu, e só então remover o usuário antigo. Nessa ordem — o inverso derruba o site.

---

## 2. Rotação de credenciais

### Por que rotacionar

Nenhuma destas apareceu no histórico do Git — o Gitleaks varreu o histórico inteiro e não
achou nada. Mas todas passaram por arquivos locais (`backend/.env`, dois `.env.backup-*`) e pelo
painel do Coolify durante a configuração. Rotacionar antes de abrir ao público é higiene,
não emergência.

**Só você deve executar.** Eu não revogo nem substituo credencial de produção.

### Ordem recomendada

Comece pelas que, se derem errado, quebram menos. Faça uma por vez e confirme o site
depois de cada uma.

| # | Credencial (nome) | Onde gerar a nova | Onde substituir | Se der errado |
|---|---|---|---|---|
| 1 | `RESEND_API_KEY` | resend.com → API Keys → Create | Coolify → variáveis do FORGE | e-mail para de sair; o app continua |
| 2 | `GEMINI_API_KEY` | aistudio.google.com → Get API key | Coolify | análise visual para; resto funciona |
| 3 | `DEEPSEEK_API_KEY` | platform.deepseek.com → API keys | Coolify | Coach para; resto funciona |
| 4 | `MP_WEBHOOK_SECRET` | Mercado Pago → sua aplicação → Webhooks → assinatura secreta | Coolify | webhooks recusados: **assinatura não ativa** |
| 5 | `MP_ACCESS_TOKEN` | Mercado Pago → Credenciais de produção | Coolify | checkout para de abrir |
| 6 | `FORGE_JWT_SECRET` | gere aleatório (abaixo) | Coolify | **todo mundo é deslogado** |
| 7 | `MONGO_URL` | Atlas → Database Access → novo usuário | Coolify | **o app não sobe** |

Para o `FORGE_JWT_SECRET`, gere assim (não reaproveite outro valor):

```
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Passo a passo de cada rotação

1. gere a chave nova no painel de origem;
2. **não revogue a antiga ainda**;
3. cole no Coolify, na variável de mesmo nome;
4. redeploy;
5. confirme: `https://forge.aiexec.com.br/api/` responde 200 e você consegue entrar;
6. rode a validação de configuração (logado como SUPER_ADMIN):

```js
(async () => {
  const t = localStorage.getItem("forge_token");
  const r = await fetch("/api/billing/config-check", { headers: { Authorization: "Bearer " + t } });
  console.table(await r.json());
})();
```

7. **só então** revogue a antiga no painel de origem.

### Cuidados específicos

**`FORGE_JWT_SECRET` desloga todo mundo.** Não é perda de dado — as pessoas entram de
novo com a mesma senha. Faça num horário de baixo movimento e avise quem estiver usando.

**`MP_WEBHOOK_SECRET` tem uma janela cega.** Entre trocar no Mercado Pago e o redeploy
terminar, webhooks chegam com assinatura que o servidor não reconhece e são recusados
(corretamente). O Mercado Pago reenvia, então nada se perde — mas não faça isso no meio
de um pagamento em andamento.

**`MONGO_URL` é a mais arriscada.** Crie o usuário novo, troque, redeploy, confirme que o
app subiu, e só então apague o usuário antigo.

### Depois de rotacionar tudo

Apague os arquivos locais que ainda carregam as chaves antigas:

```
backend/.env.backup-20260828-145124
backend/.env.backup-20260828-150633
```

Os dois estão fora do Git (`.gitignore` cobre `.env.*`), mas continuam no disco. Também
existe `memory/super_admin_invite.txt`, com um convite de administrador — ignorado pelo
Git, e sem serventia depois que a conta foi ativada.

O `backend/.env` continua necessário para rodar a suíte local. Ele aponta para o Mongo de
teste, e não para produção.

---

## 3. Conferência rápida a qualquer momento

```
gitleaks git . --no-banner --redact       # histórico: deve dar "no leaks found"
git check-ignore -v backend/.env          # deve responder com a regra que o ignora
git ls-files | grep -E "\.env"            # deve devolver apenas .env.example
```
