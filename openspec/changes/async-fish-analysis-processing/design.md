## Context

Hoje `POST /fish/analyses/process` (`backend/app/main.py`) chama `asyncio.to_thread(_sync_process_fish_analysis, ...)` e só responde quando as duas imagens terminam o `rembg` (u2net, CPU). O caminho de produção é usuário → CloudFront → nginx (EC2 frontend) → Next.js (`/api-proxy` rewrite) → backend FastAPI (EC2 privada).

Limites no caminho: CloudFront *Origin response timeout* 30 s (máx. 60 s sem cota), nginx `proxy_read_timeout` 300 s, axios 60 s (`frontend/lib/api.ts`). O primeiro a estourar é o CloudFront, que devolve 504 mesmo quando o backend conclui a análise depois (já observado antes com o download do modelo, ver change `fix-image-analysis-backend-crash`).

Restrições relevantes:
- O backend roda com `uvicorn --workers 4` (`backend/backend.Dockerfile`): estado em memória de um processo **não** é visível aos outros.
- Já ocorreu crash nativo do `onnxruntime` (processo filho morre sem traceback Python), o que deixaria um job “preso” se o estado só existisse em memória.
- Tabelas de dados de peixe usam cliente Supabase com token do usuário (RLS) — spec `fish-data-rls-enforcement`; erros ao cliente são sanitizados — spec `error-response-sanitization`.

## Goals / Non-Goals

**Goals:**
- Nenhuma requisição HTTP do fluxo de análise dura mais que alguns segundos, independentemente do tempo de processamento.
- Estado do job consistente entre workers e sobrevivente a crash de worker.
- Manter a lógica de processamento e o formato do resultado (`ProcessResponse`) inalterados para a UI.
- Isolamento por usuário via RLS e checagem em Python (defesa em profundidade).

**Non-Goals:**
- Fila externa (SQS/Celery/Redis), WebSocket/SSE, retry automático, priorização de jobs.
- Alterar o algoritmo de processamento de imagem ou o modelo `rembg`.
- Alterar Storage ou o gate de perfil.

## Decisions

**D1 — Job + polling em vez de aumentar timeouts.** O endpoint de criação responde 202 com `job_id`; o cliente consulta `GET /fish/analyses/jobs/{job_id}`. *Alternativas:* (a) só subir o timeout do CloudFront para 55 s — mitigação imediata, mas continua frágil para imagens grandes/CPU carregada e tem teto de 60 s; (b) SSE/WebSocket — exigiria mudanças no proxy do Next.js e no CloudFront, complexidade maior sem ganho para uma operação de dezenas de segundos.

**D2 — Estado do job no Postgres (Supabase), tabela `fish_analysis_jobs`.** Colunas: `id uuid pk`, `user_id uuid`, `lateral_id`, `superior_id`, `params jsonb` (fatores e peso), `status text` (`queued|processing|done|error`), `result jsonb`, `error text`, `analysis_id uuid null`, `created_at`, `started_at`, `finished_at`. RLS por `user_id` (select/insert/update do próprio usuário), seguindo o padrão de `fish_images`/`fish_analyses`. Acesso via cliente com token do usuário (`get_user_scoped_client`). *Alternativa:* dict em memória — rejeitada por causa dos 4 workers e da perda de estado em crash.

**D3 — Execução em background no mesmo processo, reutilizando `_sync_process_fish_analysis`.** Após criar o job, o endpoint agenda `asyncio.create_task` que executa a função síncrona existente via `asyncio.to_thread` e grava `processing`/`done`/`error`. A tarefa usa o `access_token` do usuário capturado na criação. Um semáforo por processo limita a concorrência (padrão 1, configurável) porque `rembg` é intensivo em CPU/memória; jobs excedentes ficam `queued` até obter o semáforo. *Alternativa:* worker dedicado/fila externa — adiada (non-goal); o desenho mantém a fronteira “criar job / executar job” para permitir essa migração depois.

**D4 — Recuperação de jobs órfãos por prazo.** Um job em `queued`/`processing` cujo `created_at` (ou `started_at`) excede `JOB_STALE_AFTER_SECONDS` (padrão 300 s) é tratado como `error` (“processamento interrompido”). A verificação ocorre de forma preguiçosa no `GET` do job e também no momento de criar novo job (para liberar a idempotência) — sem processo em segundo plano adicional. Sem retry automático: o usuário reenvia.

**D5 — Idempotência por par de imagens ativo.** Ao criar, se já existir job `queued|processing` (não obsoleto) do mesmo `user_id` com o mesmo par (`lateral_id`, `superior_id`), retorna-se o job existente (202) em vez de criar outro. Evita análises duplicadas por duplo clique/reenvio. Índice parcial em `(user_id, lateral_id, superior_id)` para status ativos.

**D6 — Resultado no próprio job (`result jsonb`).** O `ProcessResponse` (incluindo `lateral_viz_b64`/`superior_viz_b64`) é gravado em `result` ao concluir; o `GET` o devolve quando `status = done`. O registro real da análise continua em `fish_analyses` (`analysis_id` no job). *Risco:* base64 grande — ver Riscos; mitigação: limpeza de `result` após N dias e, se necessário, mover as visualizações para Storage em mudança futura.

**D7 — Erros sanitizados.** O campo `error` do job e a resposta do `GET` contêm apenas mensagens genéricas/códigos (`GENERIC_ERROR_MESSAGE` ou motivo funcional já seguro, como imagem não encontrada); detalhes vão para `logger.exception`. Erros de validação síncronos (imagem inexistente, de outro usuário) continuam retornando 404/403 no `POST`, antes de criar o job.

**D8 — Cliente com polling.** `processFishAnalysis` cria o job; `useFishAnalysis.processImages` consulta a cada 2 s (teto de ~5 min), cancela ao desmontar, propaga erro/timeout de polling ao estado `error` existente e resolve com o mesmo `ProcessResponse`. A UI ganha rótulos de progresso (“Na fila…”, “Processando…”). Falhas transitórias de rede no polling não abortam o processo (tolerar algumas falhas consecutivas).

**D9 — Compatibilidade.** `processing_status` em `fish_images` continua sendo atualizado por `_sync_process_fish_analysis` (usado por `_DashboardPage.tsx`). O contrato do `POST` muda (200 → 202); único consumidor é `frontend/lib/fishImageApi.ts`, atualizado na mesma entrega. Backend e frontend precisam ser publicados juntos.

## Risks / Trade-offs

- [Job em memória do worker perdido se o worker morrer] → D4: prazo de obsolescência marca `error`; usuário reenvia.
- [Requisições de background presas ao ciclo de vida do worker (reload/deploy)] → aceitar nesta fase; jobs interrompidos viram `error` por D4.
- [Carga: vários jobs simultâneos saturam CPU/RAM] → semáforo por processo (D3) × 4 workers = concorrência global máxima conhecida; dimensionar via configuração.
- [`result jsonb` grande (base64)] → limpeza periódica/retenção curta; questão aberta sobre Storage.
- [Token do usuário expira durante um job longo] → job curto (dezenas de segundos) e token de vida típica de 1 h; se ocorrer, job vira `error` com mensagem genérica.
- [Polling aumenta número de requisições] → intervalo de 2 s, teto de tempo, poucas dezenas de requisições por análise; custo desprezível.
- [Mudança de contrato quebra clientes antigos em cache] → publicar backend e frontend juntos; CloudFront usa cache desabilitado para o app.

## Migration Plan

1. Aplicar migração SQL (`fish_analysis_jobs` + RLS + índice) no Supabase (registrar em `backend/docs/setup_fish_images.sql`).
2. Publicar backend e frontend na mesma janela de deploy (contrato do `POST` muda).
3. Validar no ambiente CloudFront com duas imagens reais, medindo tempo total e confirmando ausência de 504.
4. Rollback: reverter imagens de backend/frontend para a versão anterior; a tabela nova pode permanecer sem efeito.

Independente disso, elevar `OriginReadTimeout` do CloudFront para 55 s como alívio imediato (infra).

## Open Questions

- Tamanho típico de `result` com as visualizações em base64 — manter em `jsonb` ou mover para Storage?
- Valores padrão: concorrência por processo (1?) e `JOB_STALE_AFTER_SECONDS` (300?) — ajustar após medir o tempo real por análise na EC2.
- Retenção de jobs concluídos: quantos dias antes de apagar/limpar `result`?
