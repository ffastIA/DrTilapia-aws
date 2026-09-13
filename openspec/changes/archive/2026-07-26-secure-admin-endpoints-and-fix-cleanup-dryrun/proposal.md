## Why

Uma auditoria de segurança encontrou duas falhas críticas em produção: (1) todos os endpoints administrativos e de chat do backend (`backend/app/main.py`) não exigem autenticação, embora as dependencies `get_current_user`/`get_current_admin_user` já existam prontas em `backend/app/dependencies.py` e nunca sejam usadas — qualquer pessoa com a URL do backend pode fazer upload, listar, deletar e limpar toda a base de conhecimento RAG; e (2) o botão "Simular Limpeza" da base vetorial promete não afetar dados, mas na verdade apaga permanentemente todos os documentos, logs de ingestão e arquivos de storage, porque `VectorAdminRepository.cleanup_vector_base` nunca verifica o parâmetro de confirmação/dry-run antes de excluir. Ambas precisam de correção imediata para evitar acesso não autorizado e perda de dados real.

## What Changes

- Proteger todos os endpoints `/admin/*` em `backend/app/main.py` com `Depends(get_current_admin_user)`.
- Proteger `/consultoria/chat` com `Depends(get_current_user)` (qualquer usuário autenticado, não precisa ser admin).
- Corrigir a cadeia `main.py` → `VectorAdminService.cleanup` → `VectorAdminRepository.cleanup_vector_base` para que o parâmetro de dry-run seja propagado corretamente por nome (não por posição).
- Implementar modo de simulação real em `cleanup_vector_base`: quando `dry_run=True`, apenas calcular e retornar as contagens do que seria deletado, sem executar nenhum delete em `documents`, `ingestion_logs`/`rag_ingestion_logs` ou no Storage.
- Manter o comportamento de exclusão real inalterado quando `dry_run=False` (confirmação explícita).
- Ajustar a mensagem de resposta da API para deixar explícito se a operação foi uma simulação ou uma execução real.

## Capabilities

### New Capabilities
- `admin-api-auth`: Exigência de autenticação/autorização (usuário autenticado ou admin, conforme o endpoint) em todos os endpoints administrativos e de chat do backend FastAPI.
- `vector-base-cleanup-dryrun`: Comportamento correto de simulação (dry-run) vs. execução real na limpeza em massa da base vetorial, incluindo relatório de contagens sem efeitos colaterais no modo simulação.

### Modified Capabilities
(nenhuma — não há specs existentes em `openspec/specs/`)

## Impact

- **Código afetado**: `backend/app/main.py` (todos os handlers `/admin/*` e `/consultoria/chat`), `backend/app/services/vector_admin_service.py` (método `cleanup`), `backend/app/vector_admin_repository.py` (método `cleanup_vector_base` e possivelmente `delete_file`/`_best_effort_delete_ingestion_logs` reaproveitados para contagem).
- **APIs**: nenhuma mudança de contrato de URL ou payload de request; endpoints passam a exigir header `Authorization: Bearer <token>` (já enviado automaticamente pelo frontend via `frontend/lib/api.ts`). Resposta de `POST /admin/vector-base/cleanup` ganha campo(s) adicionais indicando modo simulação.
- **Frontend**: nenhuma mudança de código necessária — o interceptor axios em `frontend/lib/api.ts` já injeta o Bearer token em todas as chamadas.
- **Dependências/sistemas**: nenhuma nova dependência; usa a autenticação Supabase já existente.
- **Comportamento observável**: chamadas sem token válido aos endpoints `/admin/*` e `/consultoria/chat` passam a retornar 401/403 em vez de serem executadas; clicar em "Simular Limpeza" deixa de apagar dados reais.
