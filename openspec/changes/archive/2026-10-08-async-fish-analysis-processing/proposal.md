## Why

`POST /fish/analyses/process` executa a remoção de fundo (`rembg`/u2net, em CPU) de duas imagens dentro de uma única requisição HTTP. Atrás do CloudFront, qualquer processamento acima do *Origin response timeout* (30 s por padrão, máximo 60 s sem aumento de cota) devolve **504** ao usuário, mesmo que o backend termine a análise com sucesso depois. Ajustar timeouts só adia o problema; é preciso desacoplar a duração do processamento da duração da requisição HTTP.

## What Changes

- `POST /fish/analyses/process` deixa de processar de forma síncrona: valida a entrada, cria um *job* persistido e responde **202** com `job_id` em poucos segundos.
- Novo `GET /fish/analyses/jobs/{job_id}` para consultar o estado do job (`queued` | `processing` | `done` | `error`) e, quando concluído, obter o resultado (mesmo formato do atual `ProcessResponse`).
- Nova tabela `fish_analysis_jobs` (estado durável no banco, com RLS por `user_id`), necessária porque o backend roda com múltiplos workers uvicorn.
- O processamento reutiliza a lógica existente (`_sync_process_fish_analysis`) em background, com concorrência limitada por processo.
- Jobs órfãos (worker morto/crash nativo) são marcados como `error` após um prazo, em vez de ficarem presos em `processing`.
- Chamadas repetidas para o mesmo par de imagens com job ativo do mesmo usuário retornam o job existente (idempotência).
- Frontend: `processFishAnalysis`/`processImages` passam a criar o job e fazer *polling* até a conclusão, mantendo a mesma saída (`ProcessResponse`) para a UI atual e exibindo progresso.
- **BREAKING**: o contrato de `POST /fish/analyses/process` muda (200 com resultado → 202 com `job_id`). Único consumidor conhecido: `frontend/lib/fishImageApi.ts`.
- Infra (fora do código, executada à parte): `OriginReadTimeout` do CloudFront elevado para 55 s como alívio imediato.

## Capabilities

### New Capabilities
- `async-fish-analysis-processing`: criação de job de análise, consulta de estado/resultado, isolamento por usuário, idempotência, recuperação de jobs órfãos e polling no cliente.

### Modified Capabilities
<!-- Nenhuma: os requisitos de fish-data-rls-enforcement e error-response-sanitization são apenas aplicados à nova tabela/endpoints, sem alteração de requisito. -->

## Impact

- **Backend**: `backend/app/main.py` (endpoint de processamento e novo endpoint de job), novos modelos Pydantic, novo módulo/serviço de jobs; testes em `backend/tests/`.
- **Banco (Supabase)**: nova tabela `fish_analysis_jobs` + políticas RLS (documentar em `backend/docs/setup_fish_images.sql`).
- **Frontend**: `frontend/lib/fishImageApi.ts`, `frontend/hooks/useFishAnalysis.ts`, tipos em `frontend/types/fishImage.ts` e mensagens de progresso na tela de análise.
- **Deploy/Infra**: `deploy/AWS_arquitetura_230926.md` (registrar `OriginReadTimeout` = 55 s); nenhuma mudança em nginx.
- **Fora de escopo**: fila externa (SQS/Celery), WebSocket/SSE, retry automático de jobs.
