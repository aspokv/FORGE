# FORGE — Advanced Training OS PRD

## Problema original
Aplicativo mobile-first premium para praticantes intermediários e avançados de musculação, com onboarding, avaliação muscular regional, geração de programas, registro de treino, progressão, recuperação, analytics, coach contextualizado e relatório semanal.

## Decisões de arquitetura
- React 19 + React Router-ready shell, CSS responsivo dark-first e Framer Motion.
- FastAPI + MongoDB/Motor usando MONGO_URL e DB_NAME existentes.
- Perfil sem login: localStorage versionado conceitualmente, com sincronização opcional para /api/profiles.
- Coach via GPT 5.6 Terra / Emergent LLM key, streaming SSE e prompt técnico seguro.

## Personas
- Atleta avançado autodirigido que quer decisões baseadas em performance real.
- Praticante intermediário que precisa de estrutura e progressão sem regras universais.

## Requisitos principais (estáticos)
- Onboarding em português, perfil demo, prioridades regionais e advanced mode.
- Dashboard Hoje, workout mode rápido, timer, carga/reps/RIR e persistência de séries.
- Volume por região, progressão, PRs, recovery, weekly report e coach contextual.
- Navegação mobile inferior e rail desktop; todos os controles críticos com data-testid.

## Implementado
- 2026-06-06: núcleo full-stack, API bootstrap/profiles/sets/recovery/analytics/report/coach.
- 2026-06-06: experiência visual Tactical Atelier / Iron Ledger, onboarding, dashboard, workout, progressão, análise, perfil e coach.
- 2026-06-06: demo realista de Rafael Mendes; integração real do coach com streaming.
- 2026-06-06: correção de serialização MongoDB em recovery; build, lint e teste crítico aprovados.
- 2026-06-06: V2 com Deep Athlete Assessment progressivo, 18 regiões no Muscle Map, prioridades manuais separadas de desenvolvimento e perfil novo separado do demo.
- 2026-06-06: Training Engine V2 adaptativo para 1–7 dias, microciclo de sessões com demandas HIGH/MODERATE/LOW, Priority Score, sobreposição direta/indireta e modos FORGE AUTO/ASSISTED/PRO.
- 2026-06-06: Exercise Matching, Explainable Programming, Weekly Review, upload visual com consentimento e estado explícito de Vision indisponível.
- 2026-06-06: compatibilidade corrigida para assessments legados em formato string; regressão validada com 4/4 testes públicos.

## Backlog priorizado
P0: aprovação visual do programa Assisted e Program Builder Pro com drag-and-drop persistente.
P1: persistir valores editados de carga/reps no registro, histórico por exercício completo e deload adaptativo por tendência.
P1: comparação persistente Self Assessment vs Visual Assessment quando Vision compatível estiver disponível; revisão histórica por data.
P2: autenticação opcional, exportação de dados, modo offline completo e mapa anatômico regional mais visual.

## Próximas tarefas
1. Implementar aprovação/modificação do programa Assisted antes da aplicação.
2. Expandir Program Builder Pro e análise de gargalos com persistência.
3. Conectar analytics a agregações Mongo reais e histórico de cada exercício.
4. Refinar coach com histórico de conversas persistente e controles de segurança.
