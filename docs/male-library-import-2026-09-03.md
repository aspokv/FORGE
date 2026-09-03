# Biblioteca masculina — 3 de setembro de 2026

## Escopo

Três PDFs fornecidos pelo usuário, conferidos por extração e renderização:

- `ilide.info-treino-abcde-profissional-pr_c2d6df7929709ba0be521e83cdddd9ec.pdf`: 11 páginas, uma ficha ABCDE com sete sessões/dois períodos.
- `ilide.info-untitled-pr_099ac58b3981579a9d51e99353b4694d.pdf`: 78 páginas, sete estruturas de programas e catálogo de técnicas/exercícios.
- `ilide.info-pacholok-pr_eeed2c117d9f33b46ec01d2b9ee74f25.pdf`: 12 páginas, cinco sessões. Nome público criado: Ficha de Treino ABCDE Intensivo.

Não foram redistribuídos PDFs, fotos, vídeos, biografias ou nomes de autores na interface.

## Importação

Nove novos programas em `backend/male_reference_programs.py`, todos `audience_type=male`, com filtro Masculino na biblioteca. As sete estruturas do livro são explicitamente **modelos adaptados**: o livro define posições musculares, deixando exercícios e técnicas à escolha. Não são apresentados como fichas exatas. ABCDE Estratégia 3 e ABCDE Profissional são distintos (estrutura e ficha detalhada, inclusive ordem de braços/pernas).

Dezenove variantes de exercícios adicionadas ao catálogo como `library_only=true`; não entram no conjunto de candidatos da geração automática. Nenhum treino ativo de usuário é substituído sem revisão e salvamento pelo fluxo existente.

## Limitações explícitas

- Sem duração em semanas: `0` renderiza “Duração a definir”.
- RIR ausente: valor editável 2, identificado como revisão FORGE, não informação da fonte.
- Descansos ausentes nas fichas: 90 s editáveis, com nota.
- Tempos totais são estimativas.
- Divergências entre tabelas e notas preservadas em observações (aquecimento do voador, tríceps testa, repetições das puxadas).
- Protocolo de panturrilhas remetido a vídeo não foi inventado: repetições “a definir”, revisão necessária.
- Bi/tri-sets usam o identificador suportado `superset`; composição descrita na nota.
- Puxada alta repetida em dois blocos usa seis séries no mesmo exercício para não conflitar com histórico por ID; intervalos de 30/120 s descritos e ajuste manual necessário.
- Programas profissionais mantêm blocos 1/2 em sessões distintas. O motor atual executa sequência, não agenda dois horários nem descanso automaticamente. Limitação visível antes de aplicar e nas notas preservadas no treino.
- Contagem da biblioteca agora diz “sessões”, não “dias”, evitando classificar sete sessões como sete dias de treino.

## Verificação

- 15 testes unitários de biblioteca/importação (pytest `--noconftest`, sem banco). O conftest de integração exige dependências ausentes neste ambiente; não foi execução de integração com servidor/banco.
- 250 testes frontend, incluindo clique no filtro Masculino.
- Build de produção aprovado com avisos de hooks já existentes em App.js.

## Publicação

O push anterior do commit feminino `68efe81` foi bloqueado pela revisão automática. Não repetir nem contornar sem autorização explícita do usuário para enviar ao destino `https://github.com/aspokv/FORGE.git`. Nenhum deploy é confirmado por este trabalho.
