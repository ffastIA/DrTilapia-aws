## 1. Banco de dados

- [x] 1.1 Criar a migração SQL da tabela `public.fish_analysis_jobs` (id, user_id, lateral_id, superior_id, params jsonb, status, result jsonb, error, analysis_id, created_at, started_at, finished_at) com `CHECK` em `status`
- [x] 1.2 Habilitar RLS e criar políticas `select/insert/update` do próprio usuário (mesmo padrão de `fish_images`/`fish_analyses`)
- [x] 1.3 Criar índice parcial `(user_id, lateral_id, superior_id)` para `status IN ('queued','processing')`
- [x] 1.4 Registrar o SQL em `backend/docs/setup_fish_images.sql` e aplicar no Supabase; confirmar que a tabela e as políticas existem
      — Aplicado pelo usuário via SQL Editor do Supabase Dashboard; confirmado em Table Editor: `fish_analysis_jobs` existe com as 4 políticas RLS (`select/insert/update/delete_own`).

## 2. Backend — modelos e serviço de jobs

- [x] 2.1 Adicionar modelos Pydantic: `JobCreatedResponse` (`job_id`, `status`) e `JobStatusResponse` (`status`, `analysis_id`, `result: ProcessResponse | None`, `error`)
- [x] 2.2 Criar serviço de jobs (create com idempotência, get, mark_processing/done/error, `is_stale`) usando `get_user_scoped_client`, com checagem de `user_id` em Python
- [x] 2.3 Adicionar configuração `ANALYSIS_MAX_CONCURRENCY` (padrão 1) e `JOB_STALE_AFTER_SECONDS` (padrão 300) e documentar em `backend/.env.example`

## 3. Backend — endpoints e execução

- [x] 3.1 Refatorar `POST /fish/analyses/process` para validar imagens (404/403), criar/reaproveitar o job e responder 202 com `job_id`
- [x] 3.2 Implementar execução em background (`asyncio.create_task` + `asyncio.to_thread`) reutilizando `_sync_process_fish_analysis`, com semáforo de concorrência e atualização de `queued → processing → done|error`
- [x] 3.3 Gravar `result` e `analysis_id` ao concluir; em falha, gravar `error` sanitizado (`GENERIC_ERROR_MESSAGE`) e manter `logger.exception`
- [x] 3.4 Implementar `GET /fish/analyses/jobs/{job_id}` com 404 para job inexistente/de outro usuário e marcação preguiçosa de jobs obsoletos como `error`
- [x] 3.5 Aplicar a regra de obsolescência também ao verificar idempotência na criação do job

## 4. Testes do backend

- [x] 4.1 Testes de criação: 202 imediato, 404/403 sem criar job, idempotência (mesmo `job_id` para duplo envio) e novo job após `done`/`error`
- [x] 4.2 Testes de status: `queued/processing/done/error`, resultado com o mesmo formato do `ProcessResponse`, erro sem detalhes internos
- [x] 4.3 Testes de isolamento: job de outro usuário retorna 404
- [x] 4.4 Teste de job obsoleto marcado como `error` e teste do limite de concorrência
- [ ] 4.5 Rodar a suíte `pytest` completa e confirmar ausência de regressões
      — `backend/tests/test_fish_analysis_jobs.py` escrito (14 testes); a suíte completa não terminou de rodar nesta sessão (import da app está muito lento neste ambiente Windows/OneDrive — provável varredura de antivírus nos pacotes de ML). Rodar `pytest` localmente antes do deploy.

## 5. Frontend

- [x] 5.1 Atualizar tipos em `frontend/types/fishImage.ts` (job criado, status do job) e `processFishAnalysis` em `frontend/lib/fishImageApi.ts` para criar o job; adicionar `getFishAnalysisJob`
- [x] 5.2 Implementar polling em `processImages` (`frontend/hooks/useFishAnalysis.ts`): intervalo de 2 s, teto de ~5 min, cancelamento no unmount, tolerância a falhas de rede consecutivas
- [x] 5.3 Exibir estado de progresso (“Na fila…”, “Processando…”) na tela de análise e tratar `error` e tempo excedido com opção de tentar novamente
- [x] 5.4 Garantir que o retorno de `processImages` continue sendo `ProcessResponse`, sem alterar o restante da UI

## 6. Deploy e verificação

- [x] 6.1 Elevar o `OriginReadTimeout` do CloudFront para 55 s e registrar o valor em `deploy/AWS_arquitetura_230926.md`
      — Aplicado direto na distribuição `EDBXN5YJME58R` via AWS CLI (status `Deployed`) e registrado no doc.
- [ ] 6.2 Aplicar a migração no Supabase e publicar backend e frontend na mesma janela (mudança de contrato do `POST`)
      — Migração no Supabase aplicada (ver 1.4). Falta publicar backend+frontend juntos (`.\deploy\build-and-push.ps1` + pull/up nas duas EC2s).
- [ ] 6.3 Teste real no navegador via CloudFront com duas imagens reais: análise conclui sem 504, medir tempo total e confirmar exibição do resultado
- [ ] 6.4 Teste real de duplo clique e de recarregar a página durante o processamento; confirmar que só uma análise é criada
- [ ] 6.5 Ajustar valores padrão de concorrência e de obsolescência conforme o tempo medido e registrar as conclusões nas Open Questions do `design.md`
