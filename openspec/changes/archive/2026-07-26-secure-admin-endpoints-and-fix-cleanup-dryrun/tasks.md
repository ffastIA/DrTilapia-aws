## 1. Proteger endpoints administrativos

- [x] 1.1 Em `backend/app/main.py`, importar `get_current_user` e `get_current_admin_user` de `app.dependencies`.
- [x] 1.2 Adicionar `admin: dict = Depends(get_current_admin_user)` como parâmetro em `upload_admin` (`POST /admin/upload`).
- [x] 1.3 Adicionar `admin: dict = Depends(get_current_admin_user)` em `get_vector_files` (`GET /admin/vector-base/files`).
- [x] 1.4 Adicionar `admin: dict = Depends(get_current_admin_user)` em `get_vector_file` (`GET /admin/vector-base/files/{original_file_id}`).
- [x] 1.5 Adicionar `admin: dict = Depends(get_current_admin_user)` em `get_vector_file_chunks` (`GET /admin/vector-base/files/{original_file_id}/chunks`).
- [x] 1.6 Adicionar `admin: dict = Depends(get_current_admin_user)` em `get_vector_file_content` (`GET /admin/vector-base/files/{original_file_id}/content`).
- [x] 1.7 Adicionar `admin: dict = Depends(get_current_admin_user)` em `get_vector_file_diagnosis` (`GET /admin/vector-base/files/{original_file_id}/diagnosis`).
- [x] 1.8 Adicionar `admin: dict = Depends(get_current_admin_user)` em `delete_vector_file` (`POST /admin/vector-base/files/{original_file_id}/delete`).
- [x] 1.9 Adicionar `admin: dict = Depends(get_current_admin_user)` em `cleanup_vector_base` (`POST /admin/vector-base/cleanup`).
- [x] 1.10 Adicionar `admin: dict = Depends(get_current_admin_user)` em `reindex_vector_base` (`POST /admin/vector-base/reindex`).

## 2. Proteger endpoint de chat

- [x] 2.1 Adicionar `user: dict = Depends(get_current_user)` como parâmetro em `chat` (`POST /consultoria/chat`), sem exigir role admin.

## 3. Corrigir propagação do dry-run no cleanup da base vetorial

- [x] 3.1 Em `backend/app/services/vector_admin_service.py`, alterar `cleanup(self, dry_run: bool = True)` para chamar o repositório passando `dry_run` explicitamente por nome (kwarg), não posicionalmente, eliminando a ambiguidade que hoje o mapeia para `confirmation_phrase`.
- [x] 3.2 Em `backend/app/vector_admin_repository.py`, alterar a assinatura de `cleanup_vector_base` de `(self, confirmation_phrase: str)` para `(self, dry_run: bool = True)`.
- [x] 3.3 Dentro de `cleanup_vector_base`, quando `dry_run=True`: usar `list_files()` para obter os arquivos válidos e somar `total_chunks` (equivalente a documentos que seriam deletados) e contar arquivos com `storage_bucket`/`storage_path` preenchidos (equivalente a objetos de Storage que seriam removidos), SEM chamar `delete_file`, sem deletar de `documents`, `ingestion_logs`/`rag_ingestion_logs`, nem do Storage.
- [x] 3.4 Dentro de `cleanup_vector_base`, quando `dry_run=False`: manter o comportamento atual — iterar os arquivos e chamar `delete_file(fid, ..., hard_delete=True)` para cada um, deletando de verdade `documents`, logs de ingestão e Storage.
- [x] 3.5 Incluir no dicionário de retorno de `cleanup_vector_base` um campo `dry_run: bool` refletindo o modo executado, e ajustar a mensagem (`message`) para deixar explícito se foi "simulação" ou "execução real".
- [x] 3.6 Em `backend/app/main.py`, na função `_normalize_cleanup_response`, propagar o novo campo `dry_run` do resultado do repositório para o payload de `CleanupVectorBaseResponse` (ajustando `backend/app/vector_admin_schemas.py` se o schema `CleanupVectorBaseResponse` precisar do novo campo `dry_run`).

## 4. Verificação manual

- [x] 4.1 Rodar o backend localmente e, sem header `Authorization`, confirmar que cada endpoint `/admin/*` e `/consultoria/chat` retorna 401. Verificado ao vivo (desbloqueado pela mudança `fix-langchain-dependency-mismatch`): `/admin/vector-base/files`, `/admin/upload`, `/admin/vector-base/cleanup` e `/consultoria/chat` retornaram `401 {"detail":"Token de acesso não fornecido"}`.
- [x] 4.2 Autenticar como usuário não-admin (`role='user'`) e confirmar que os endpoints `/admin/*` retornam 403, e que `/consultoria/chat` funciona normalmente. Verificado ao vivo contra o projeto Supabase real: `/admin/vector-base/files` com token de usuário comum → **403**. `/consultoria/chat` com token de usuário comum → passou pela autenticação (camada validada), mas revelou um bug pré-existente não relacionado (RPC `match_documents` inexistente no banco — ver nota na mudança `isolate-login-client-and-fix-users-rls`). Esta validação só foi possível depois de corrigir, em mudança separada, o bug de vazamento de privilégio do cliente Supabase compartilhado (`isolate-login-client-and-fix-users-rls`), descoberto durante este próprio teste.
- [x] 4.3 Autenticar como admin e confirmar que os endpoints `/admin/*` funcionam normalmente. Verificado ao vivo: `GET /admin/vector-base/files` com token de admin → **200**, listou corretamente os 4 arquivos reais da base (49 chunks). `POST /admin/vector-base/cleanup` (dry-run e real) também confirmados no item 4.4/4.5 abaixo.
- [x] 4.4 Com a base vetorial contendo arquivos reais (4 arquivos, 49 chunks), chamado `POST /admin/vector-base/cleanup` em modo simulação (`dry_run=true`) — resposta reportou corretamente "4 arquivo(s), 49 documento(s) SERIAM removidos", e `GET /admin/vector-base/files` confirmou os 4 arquivos intactos depois. Confirmado com dados reais de produção, com segurança (dry-run não altera nada).
- [x] 4.5 Chamado `POST /admin/vector-base/cleanup` com confirmação real (`confirmation_phrase="CONFIRMADO"`, `dry_run=false`), autorizado explicitamente pelo usuário sabendo que afetaria os 4 arquivos reais. A resposta confirmou ter tomado o ramo de execução real (`dry_run: false`, mensagem "dados removidos permanentemente"), mas reportou `total_documents_deleted: 0` — e de fato nenhum documento foi removido (confirmado via `GET /admin/vector-base/files`, os 4 arquivos com todos os chunks continuam intactos). **Causa raiz (bug novo, pré-existente, fora do escopo desta mudança):** os 49 registros de `documents` têm a coluna de topo `original_file_id` como `NULL` — o valor real só existe dentro da coluna `metadata` (jsonb). `VectorAdminRepository.delete_file` filtra a exclusão com `.eq('original_file_id', ...)` na coluna de topo, que nunca casa com nenhuma linha para estes dados legados, tornando a exclusão (individual e em massa) um no-op silencioso. Resultado prático: a correção do roteamento dry-run-vs-real está validada (o código realmente entra no ramo de exclusão real quando confirmado, em vez de simular), mas a exclusão em si está quebrada para dados ingeridos neste formato — registrado como achado novo a ser corrigido em uma mudança futura. Os 4 arquivos reais permaneceram 100% intactos durante todo o teste.
