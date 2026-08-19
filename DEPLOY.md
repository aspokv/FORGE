# FORGE — migração Railway → VPS (Coolify em panel.aiex.com.br)

## Estado atual

| Peça | Onde está |
|---|---|
| Backend FastAPI | Railway — `forge-production-8570.up.railway.app` (free). `/docs` responde 200 |
| Frontend CRA | **host desconhecido** — não há `.vercel`, `vercel.json`, `netlify.toml` nem `railway.json` no repo |
| MongoDB | Atlas (confirmar no Railway → Variables: host terminando em `.mongodb.net`) |

**Decisão:** o Atlas fica onde está. Colocar banco + app numa VPS de 2 vCPU é risco sem
ganho. A VPS roda só a aplicação.

---

## A pergunta que precisa de resposta antes de desligar o Railway

**Onde está publicado o frontend hoje?** Se ele for um segundo serviço no Railway, deletar
o projeto derruba o app inteiro mesmo com o backend já migrado. Confira a lista de serviços
do projeto no Railway antes do passo final.

Se o front estiver no Railway → suba os dois na VPS (Opção A abaixo) e delete o projeto
inteiro de uma vez.

---

## Opção A — front + backend na VPS, um domínio só (recomendada)

É o que os arquivos deste repo implementam: `docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`, `frontend/nginx.conf`.

nginx serve o SPA em `/` e faz proxy de `/api` para o backend pela rede interna.

Ganhos concretos:
- **CORS deixa de existir** — mesma origem.
- **A URL da API vira relativa** (`/api`). O CRA congela `REACT_APP_BACKEND_URL` dentro do
  bundle em tempo de build; com string vazia não há mais URL de backend embutida, então
  trocar de domínio nunca mais exige rebuild.
- **Um domínio só**, um certificado só, e o Railway pode ser deletado por completo.
- Backend não fica exposto na internet.

### Configuração no Coolify

New Resource → **Docker Compose** → Private Repository (GitHub App)

| Campo | Valor |
|---|---|
| Repositório | `aspokv/FORGE` |
| Branch | `main` |
| Docker Compose Location | `/docker-compose.yml` |
| Domínio | apenas no serviço **frontend**, porta **80** |
| Auto Deploy | ativado |

Sem Start Command, sem Base Directory, sem Port Exposes manual — tudo isso está nos
Dockerfiles.

## Opção B — só o backend, com domínio separado (o plano do outro assistente)

Válida se o frontend estiver fora do Railway e você quiser mexer no mínimo agora.

New Resource → Private Repository → Build Pack: **Dockerfile** (não Railpack — ver abaixo)

| Campo | Valor |
|---|---|
| Base Directory | `/backend` |
| Dockerfile Location | `/backend/Dockerfile` |
| Port Exposes | `8000` |
| Start Command | **deixe vazio** — já está no Dockerfile |
| Domínio | `api-forge.aiex.com.br` |

Depois: `CORS_ORIGINS=https://<origem-do-frontend>` e rebuild do frontend com
`REACT_APP_BACKEND_URL=https://api-forge.aiex.com.br`.

### Por que Dockerfile em vez de Railpack

- O Railpack escolhe a versão do Python por heurística. O projeto roda em **3.11** e o
  `requirements.txt` fixa `motor==3.3.1`, `pymongo==4.6.3`, `bcrypt==4.1.3` — versão de
  runtime diferente é fonte de erro de wheel/binário. O Dockerfile fixa 3.11-slim.
- **`${PORT:-3000}` no Start Command é uma armadilha.** Se o Coolify executar o comando sem
  shell, `${PORT:-3000}` chega literal ao uvicorn e o container morre com
  `invalid int value`. Com Dockerfile a porta é fixa (8000) e não existe variável `PORT`.
- `PORT=3000` é variável injetada pela Railway. **Não copie para o Coolify** — não serve
  para nada aqui e só cria a chance de erro acima.

---

## Variáveis de ambiente

Copie do Railway (Variables → Raw Editor) **apenas estas sete** — o resto (`PORT`,
`RAILWAY_*`) é lixo específico da plataforma:

```
MONGO_URL=<a string do Atlas, idêntica à do Railway>
DB_NAME=<idêntico ao do Railway>
FORGE_JWT_SECRET=<o ATUAL, não gere outro>
FORGE_SUPER_ADMIN_EMAIL=nicolas.ms13@gmail.com
DEEPSEEK_API_KEY=<a mesma>
GEMINI_API_KEY=<a mesma>
CORS_ORIGINS=<Opção A: o domínio único | Opção B: a origem do frontend>
```

- `FORGE_JWT_SECRET` novo invalida todo token emitido — todo mundo é deslogado. Mantenha o atual.
- `DB_NAME` errado não dá erro: o app sobe apontando para um banco vazio e parece que os
  dados sumiram. Confira caractere por caractere.
- `CORS_ORIGINS="*"` funciona (o app autentica por Bearer token, não por cookie), mas
  prefira a origem exata.
- **Libere o IP da VPS no Atlas → Network Access**, senão o backend sobe e falha em toda
  query.

---

## Ordem de corte (não derruba o app em nenhum momento)

1. Railway continua no ar, intocado.
2. Deploy na VPS e teste pelo domínio temporário do Coolify.
3. DNS no Cloudflare: `A` → IP da VPS, **Proxy DNS Only** (a nuvem laranja quebra a emissão
   do Let's Encrypt no primeiro deploy).
4. Domínio definitivo no Coolify, certificado emitido.
5. (Opção B) rebuild do frontend com a nova URL.
6. Bateria de testes em produção.
7. Backup das variáveis do Railway (print do Raw Editor já basta).
8. **Só então** delete o projeto no Railway — depois de confirmar que o frontend não mora lá.

## Testes obrigatórios antes do corte

```bash
curl -i https://<dominio>/api/     # 200
curl -i https://<dominio>/         # 200, index.html do SPA
```

No navegador: login, cadastro, gerar treino, **substituir exercício** (persistência),
**Concluir treino** (a sessão tem que avançar — `POST /api/workout/complete`), gerar plano
de nutrição, painel admin, e uma mensagem no **Coach**.

O Coach é o teste mais importante: é SSE (`POST /api/coach`, `text/event-stream`). Se a
resposta chegar de uma vez só, em bloco, em vez de streaming, o buffer do proxy está
ligado — no nginx é o `proxy_buffering off` do `frontend/nginx.conf`; no Cloudflare, ligar
a nuvem laranja pode reintroduzir buffering (o backend já manda `X-Accel-Buffering: no`,
que o nginx respeita).

Reinicie o container e refaça o login para provar persistência (os dados estão no Atlas,
então devem sobreviver — se não sobreviverem, `DB_NAME` está errado).

---

## Armadilhas desta stack

- **Build do frontend consome ~1,5 GB de RAM.** Numa VPS de 2 vCPU/2 GB o `yarn build`
  pode morrer por OOM sem mensagem clara. Ative 2 GB de swap antes do primeiro deploy.
- **`backend/.env` está no `.dockerignore`** de propósito: os valores locais são de dev
  (`mongodb://localhost:27017`, `test_database`) e derrubariam o container em produção.
- **`server.py` lê `os.environ["MONGO_URL"]` no import** — faltando a variável, falha no
  boot, não em runtime. O log mostra `KeyError: 'MONGO_URL'`.
- **`requirements.txt` carrega dev tools** (black, flake8, mypy, pytest) e
  `pandas`/`numpy`/`boto3`, que nenhum módulo do backend importa. Não mexi para não
  arriscar o build, mas cortar isso reduz muito o tempo de build e o tamanho da imagem.
