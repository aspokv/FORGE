# Astra 6 — entrega aprovada

## Atualização de entrega

O usuário aprovou a implementação atual das cinco telas e autorizou concluir testes frontend, build, smoke check, publicação da branch, PR, checks, merge e deploy existente. Não é necessária uma nova auditoria visual completa.

- Dependências frontend instaladas com Yarn 1.22.22, `--frozen-lockfile` e cache no workspace. `package.json` e `yarn.lock` permanecem inalterados.
- **484 testes frontend passaram, em 33 suítes**, com `CI=true yarn test --watchAll=false --runInBand`.
- Os **400 testes locais anteriores** permanecem como evidência aceita; não foram repetidos nesta entrega.
- **Build de produção passou** com `CI=false yarn build`, conforme o comando do CI existente. Foram emitidos sete avisos `react-hooks/exhaustive-deps` nos fluxos existentes de `App.js`; nenhum erro de compilação.
- Smoke check: os testes de interação das cinco telas passaram; os 37 arquivos do manifesto existem; os bundles JavaScript são sintaticamente válidos; as cinco telas e a navegação estão incluídas; fixtures do teste não aparecem no bundle. Esse check de artefatos não mede overflow em um navegador real.
- A única correção após a aprovação foi completar `actual.foods` na fixture do teste de nutrição. Não houve alteração de design, lógica do aplicativo ou dependências.
- **Produção: Hostinger VPS + Coolify existente**, branch `main`, domínio `forge.aiexec.com.br`. Os status legados da Railway devem ser ignorados. Não criar infraestrutura nem alterar DNS.
- O Git HTTPS não possui credencial local. A conexão GitHub autenticada tem permissão de escrita e será usada para publicar o mesmo conteúdo da branch oficial, mantendo o parent oficial e verificando a igualdade do tree SHA.

## Histórico anterior à aprovação final

As pendências abaixo registram a execução anterior. O status atual de testes frontend/build e o escopo de validação são os da atualização acima.

Esta branch ainda não está pronta para publicação. A implementação das cinco telas está no clone oficial, mas testes frontend, build, regressões com banco e comparação visual ainda precisam passar. Não há afirmação de equivalência visual validada.

## Identificação

| Campo | Valor |
|---|---|
| Repositório | `aspokv/FORGE` |
| Diretório oficial | `/workspace/scratch/f622b4bc57b2/FORGE-official` |
| Origin, fetch e push | `https://github.com/aspokv/FORGE.git` |
| Branch base | `main` |
| SHA inicial da main | `0269109a536862c4f7c4120152472d37a90b58c5` |
| Branch implementada | `feat/astra6-exact-implementation` |
| Referência anterior às tentativas rejeitadas | `2804f433024bc8038ac07d746fea0b14c8271691` |
| Novos commits | Nenhum; alterações locais preservadas |
| Push / PR / merge / deploy | Não realizados |
| Merge SHA | Não aplicável |
| URL validada | Nenhuma |

O clone foi obtido diretamente do GitHub. Foram verificados remote, status, branch e histórico; `main` foi atualizada com fast-forward antes da criação da branch. Nenhum histórico do ZIP foi usado. Na inspeção inicial, não havia commits funcionais posteriores ao merge informado pelo usuário. O diff contra a referência limpa continha os cinco arquivos visuais informados, sem exigir reset.

## Fonte visual

Arquivos do pacote entregue pelo usuário, extraídos em `../astra-source/`:

| Arquivo | SHA-256 |
|---|---|
| `FORGE-HTML-Static.html` | `84414f39b9851f6ba00bcf0e7fcdd12da2abb62b03e716f4f871ae2db1f4dc6c` |
| `FORGE-Prancha-Final.jpg` | `4bc3d4bddf40814c24096abb24c78802354481fc05022e57ee8a1bfddcd6da91` |

Tokens, composição, tipografia, ícones e medidas foram transcritos do HTML para classes isoladas `a6-*`. A folha rejeitada `astra-visual.css` foi removida. O React e os contratos de dados continuam sendo os do aplicativo. Fixtures adicionadas nesta mudança estão exclusivamente em arquivos de teste.

## Mapeamento e alterações

| Astra | Componente real | Estado implementado, ainda sem validação visual |
|---|---|---|
| Início | `ReferenceHome` | Data e nome reais, hero existente, sobreposição da sessão ativa, CTA com check-in, semana do programa, dias com séries registradas, consumo alimentar e hidratação. |
| Treino | `ReferenceWorkoutPreview` e fluxo existente em `App.js` | Resumo, mapa muscular, aquecimento, todos os exercícios, séries/reps/RIR prescritos, assets existentes, abertura da biblioteca e início da sessão. O registro, substituição, conclusão e próxima sessão mantêm seus handlers. |
| Nutrição | `Nutrition`, `AstraNutritionSummary`, `NutritionDailyFooter` | Gauge e macros calculados do diário real; todas as refeições em cards compactos; detalhes mantêm registro, troca e edição; hidratação conserva atualização, desfazer e erros. |
| Progresso | `Progress`, `AstraProgress`, `WeightTracker`, `ProgressPhotos` | Tabs de carga/peso/fotos; gráfico calculado dos pontos de analytics, melhores marcas e calendário real; detalhes extras continuam acessíveis. Sem pontos suficientes, aparece um estado vazio explícito. |
| Perfil | `Profile` | Resumo real, grupos Seu treino/Sua conta, preferências e programa atrás das opções, avaliação, plano, análise e saída. Callbacks e salvamento existentes preservados. |
| Navegação | `AthleteShell`, `AstraBottomNav` | Os mesmos destinos de estado do aplicativo; barra Astra nas cinco telas e navegação existente nos demais fluxos. |

Foi adicionado um teste de interação com oito casos para Home/check-in, treino/biblioteca, registro alimentar, hidratação/erros, progresso, perfil e navegação. Ele ainda não pôde ser executado.

## Assets

Preservados: logo/chama em `forge-home-hero.jpg`, hero em `forge-home-athlete-reference.jpg`, fotos de refeições existentes, mapas musculares e pipeline `ExercisePhoto` com assets WebP reais. A comparação dos bytes das imagens embutidas no HTML encontrou os arquivos correspondentes já existentes no repositório.

Assets adicionados: nenhum. Os thumbnails usam proporção preservada; o recorte final ainda requer inspeção no navegador.

## Arquivos alterados

- `frontend/src/App.js`
- `frontend/src/index.js`
- `frontend/src/astra-visual.css` — removido
- `frontend/src/astra6-exact.css` — novo
- `frontend/src/features/AstraUI.jsx` — novo
- `frontend/src/features/AstraNutritionSummary.jsx` — novo
- `frontend/src/features/AstraProgress.jsx` — novo
- `frontend/src/features/Astra.integration.test.js` — novo
- `frontend/src/features/ReferenceHome.jsx`
- `frontend/src/features/ReferenceHome.artwork.test.js`
- `frontend/src/features/ReferenceWorkoutPreview.jsx`
- `frontend/src/features/ReferenceWorkoutPreview.content.test.js`
- `frontend/src/features/Nutrition.jsx`
- `frontend/src/features/NutritionDailyFooter.jsx`
- `backend/tests/test_training_engine_v4.py` — correção do cenário do teste, sem alteração do motor
- `docs/astra6-implementation.md`

## Testes e build

| Verificação | Resultado |
|---|---|
| Suíte de training engine usada pelo CI | **88 passaram** |
| Regressões locais adicionais de nutrição, treino v4 e parser/importação | **312 passaram** |
| Análise sintática dos nove arquivos JSX de implementação/teste | Passou antes da interrupção da sessão de instalação |
| `git diff --check` | Passou |
| Instalação frontend conforme lockfile | Incompleta |
| Testes frontend, incluindo os novos | Não executados: dependências indisponíveis |
| Build real frontend | Não executado: dependências indisponíveis |
| Regressões com servidor e MongoDB reais | Não iniciaram: MongoDB encerrou na inicialização |

Os dois grupos aprovados acima são testes locais sem servidor (`--noconftest`), não evidência de validação ponta a ponta de login/cadastro, treino, nutrição ou pagamentos.

A suíte adicional inicialmente apresentou uma falha no teste de ordenação de bíceps. O cenário posicionava Pull no índice zero de um ciclo Push/Pull/Legs, que o motor interpreta como Push. O teste foi corrigido para usar o ciclo real de três dias e alterar a sessão Pull no índice um. A asserção original foi mantida e um controle positivo confirma que o aviso desaparece ao corrigir a ordem dos exercícios. Nenhum código de negócio do backend foi alterado.

Comandos dos grupos aprovados, a partir de `backend/`, usando as dependências Python já instaladas:

```bash
PYTHONPATH=../.venv/lib/python3.12/site-packages:. python -m pytest -q --noconftest \
  tests/test_training_engine_v5.py tests/test_training_personalization.py \
  tests/test_engine_v2.py tests/test_engine_v3.py tests/test_exercise_photo_coverage.py

PYTHONPATH=../.venv/lib/python3.12/site-packages:. python -m pytest -q --noconftest \
  tests/test_nutrition_guided_flow.py tests/test_nutrition_dna.py \
  tests/test_nutrition_substitution_dna.py tests/test_nutrition_real_meal_composition.py \
  tests/test_nutrition_portion_hierarchy.py tests/test_nutrition_periodization.py \
  tests/test_nutrition_directional.py tests/test_food_substitution.py \
  tests/test_cutting_intensity.py tests/test_bulking_intensity.py \
  tests/test_manual_workout_parser.py tests/test_training_engine_v4.py \
  tests/test_nutrition_import.py
```

## Bloqueios verificados

1. **Instalação frontend:** `corepack yarn install --frozen-lockfile --network-timeout 60000` chegou à etapa de download. A sessão foi encerrada antes da conclusão e o cache temporário fora do workspace não persistiu. A tentativa seguinte terminou com `network approval was cancelled before a decision was returned`. Não houve nova tentativa de contornar ou repetir a aprovação. `frontend/node_modules` não existe na verificação final.
2. **Banco local de integração:** MongoDB 8.0.4 foi baixado e seu executável verificado. A inicialização de um banco descartável, em `127.0.0.1:27028`, falhou com `open: Operation not permitted`, código 100. O backend e a suíte com banco não chegaram a iniciar. Produção não foi acessada.
3. **Comparação visual:** o navegador recusou abrir o HTML local pela política de URLs. Não foram tentadas prévias externas, superfícies alternativas ou contornos do bloqueio. Nenhuma captura da aplicação foi obtida.

## Responsividade e diferenças restantes

| Largura | Comparação com a prancha | Overflow, recorte e toque |
|---|---|---|
| 390 px | Pendente | Não confirmado |
| 360 px | Pendente | Não confirmado |
| 375 px | Pendente | Não confirmado |
| 412 px | Pendente | Não confirmado |
| Desktop | Pendente | Não confirmado |

As regras CSS seguem as medidas do HTML e reservam espaço para a navegação. Isso não substitui a inspeção do DOM renderizado, a comparação visual e os testes de toque.

Diferenças deliberadas que precisam ser avaliadas com os dados reais:

- Não há relógio/status bar fictícios do mockup dentro do aplicativo; são áreas do sistema operacional.
- Quantidade de exercícios/refeições, nomes, semana, números e curvas vêm do produto real. Não são truncados para imitar os dados demonstrativos.
- Dados insuficientes no progresso mostram estado vazio, sem inventar evolução.
- Edição de refeições, preferências, hidratação e análises adicionais ficam acessíveis por opções expansíveis.
- Thumbnails de exercícios preservam a imagem completa com `object-fit: contain`; a referência usa recorte. Essa diferença permanece para avaliação visual.

Outras diferenças de espaçamento, densidade, alinhamento ou recorte ainda não puderam ser identificadas ou descartadas. As cinco telas não devem ser declaradas visualmente equivalentes antes dessa etapa.

## CI e deploy existente

Foram lidos `DEPLOY.md`, `docker-compose.yml`, os Dockerfiles e `.github/workflows/training-engine-ci.yml`. O fluxo documentado usa o serviço existente no Coolify com Docker Compose a partir de `main`, frontend Nginx e backend interno, mantendo o MongoDB Atlas. A documentação contém referências históricas ao Railway; o serviço ativo e sua configuração ainda precisam ser confirmados no painel existente antes de qualquer merge.

Não foi criada infraestrutura. Não foram usados tokens de pagamento como credenciais de deploy. Não houve verificação autenticada do Coolify nem tentativa de deploy. O domínio informado pelo usuário é `forge.aiexec.com.br`; ele não foi validado nesta execução.

## Continuação

Conservar esta branch e as alterações locais. Em ambiente que permita instalação, usar o lockfile sem regenerá-lo e manter o cache do Yarn dentro do workspace para não perder downloads. Executar toda a suíte frontend e o build, corrigir falhas, rodar as integrações em Mongo descartável e comparar as cinco telas com a prancha em 390/360/375/412 px e desktop. Só depois dos gates completos: commit, push, PR, checks, merge e acompanhamento do serviço de deploy já existente.
