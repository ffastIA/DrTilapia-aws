## Context

O backend FastAPI (`backend/app/main.py`) expõe endpoints administrativos (upload de PDF, listagem/leitura/exclusão/limpeza/reindexação da base vetorial) e o endpoint de chat de consultoria sem nenhuma verificação de autenticação. As dependencies `get_current_user` e `get_current_admin_user` (`backend/app/dependencies.py`) já existem, validam o JWT do Supabase via `supabase.auth.get_user(access_token)` e consultam a tabela `users` para checar `role`, mas nunca são injetadas nas rotas. O frontend já autentica via Supabase Auth e o axios interceptor (`frontend/lib/api.ts:16-28`) já anexa `Authorization: Bearer <token>` em toda chamada, então a peça que falta é só o lado do servidor.

Separadamente, `POST /admin/vector-base/cleanup` tem um bug de perda de dados: `vector_admin_service.cleanup(dry_run)` (`backend/app/services/vector_admin_service.py:81-83`) despacha dinamicamente para `VectorAdminRepository.cleanup_vector_base(self, confirmation_phrase)` (`backend/app/vector_admin_repository.py:348-375`) passando `dry_run` (bool) posicionalmente no lugar de `confirmation_phrase` (str). O método nunca lê esse parâmetro — ele sempre lista todos os arquivos e chama `delete_file(fid, confirmation_phrase, hard_delete=True)` para cada um, apagando `documents`, tentando apagar `ingestion_logs`/`rag_ingestion_logs` e removendo objetos do Storage. Ou seja, hoje **toda chamada a cleanup apaga tudo de verdade**, independente do modo escolhido na UI.

## Goals / Non-Goals

**Goals:**
- Fazer todo endpoint `/admin/*` exigir um usuário autenticado com `role == 'admin'`.
- Fazer `/consultoria/chat` exigir qualquer usuário autenticado (admin ou não).
- Garantir que `dry_run=True` (ou `confirmation_phrase != "CONFIRMADO"`) no cleanup da base vetorial nunca produza um delete real em `documents`, `ingestion_logs`/`rag_ingestion_logs` ou Storage — apenas retorna contagens do que seria afetado.
- Preservar o comportamento de exclusão real existente quando a limpeza é explicitamente confirmada.
- Manter compatibilidade com o payload que o frontend já envia (`ragAdminApi.ts`), sem exigir mudanças no frontend.

**Non-Goals:**
- Não implementar refresh de token, RBAC granular por recurso, ou rate limiting — fora do escopo desta correção pontual.
- Não corrigir o endpoint de reindexação quebrado (`reindex_files` ausente no repositório) — é um problema funcional separado, já registrado na auditoria, não coberto por esta mudança.
- Não migrar CORS `allow_origins=["*"]` nem outras melhorias de média prioridade da auditoria — tratadas em mudanças futuras.
- Não alterar o esquema de resposta dos demais endpoints além do necessário para expor o modo simulação no cleanup.

## Decisions

1. **Usar as dependencies já existentes em `dependencies.py` via `Depends(...)` no assinatura de cada rota**, em vez de um middleware global de autenticação.
   - Alternativa considerada: middleware FastAPI aplicado a todas as rotas `/admin/*` por prefixo. Rejeitada porque exigiria roteador separado (`APIRouter` com prefixo) — mudança maior de estrutura para um fix que deve ser cirúrgico; `Depends` por rota é explícito, testável endpoint a endpoint, e já é o padrão que o próprio código-base já definiu em `dependencies.py`.
   - `/consultoria/chat` usa `get_current_user` (qualquer usuário logado); todos os `/admin/*` usam `get_current_admin_user` (somente role admin), refletindo exatamente os dois níveis de acesso já modelados nas dependencies.

2. **Corrigir a propagação do dry-run usando keyword arguments explícitos entre as camadas**, abandonando o dispatch puramente posicional para este método específico.
   - `main.py` continua calculando `dry_run` a partir de `request.dry_run`/`request.confirmation_phrase` como hoje.
   - `VectorAdminService.cleanup(dry_run: bool)` passa a chamar o repositório com `dry_run=dry_run` por nome (usando `_call_repo_method` com kwargs, ou uma chamada direta tipada — decisão de implementação em tasks.md), eliminando a ambiguidade posicional que causou o bug.
   - `VectorAdminRepository.cleanup_vector_base(self, dry_run: bool)` passa a receber e honrar esse parâmetro diretamente. O parâmetro `confirmation_phrase` deixa de ser necessário nessa função (a decisão simulação-vs-execução já foi tomada em `main.py`); simplifica a assinatura em vez de manter dois parâmetros que podem voltar a divergir.
   - Alternativa considerada: manter `confirmation_phrase: str` e comparar `== "CONFIRMADO"` dentro do repositório. Rejeitada porque duplicaria a lógica de decisão dry-run/confirmação que já existe em `main.py` (`main.py:179`), voltando a criar duas fontes de verdade para o mesmo booleano — exatamente o padrão que gerou o bug original.

3. **Modo dry-run reutiliza a mesma lógica de agrupamento (`list_files`/`_group_valid_rows_by_file`) para calcular contagens, sem chamar `delete_file` nem tocar no Storage.**
   - Para cada arquivo listado, soma `total_chunks` (equivalente ao que seria removido de `documents`) e verifica presença de `storage_bucket`/`storage_path` para contar quantos arquivos de Storage seriam removidos. Não faz nenhuma chamada de `.delete()` ou `.storage.remove()`.
   - Isso mantém a resposta (`total_files_processed`, `total_documents_deleted`, `total_storage_deleted`, etc.) com a mesma forma usada hoje, mas os números passam a significar "seria deletado" em vez de "foi deletado" quando `dry_run=True`. Um novo campo `dry_run: bool` (ou `simulated: bool`) é adicionado à resposta para desambiguar explicitamente para quem consome a API.

## Risks / Trade-offs

- **[Risco] Frontend em produção pode ter sessões antigas sem token válido armazenado** → Mitigação: o interceptor de resposta do axios (`frontend/lib/api.ts:31-40`) já trata 401 limpando o auth store; usuários serão redirecionados ao login, comportamento esperado e já implementado.
- **[Risco] Usuários que hoje usam o admin sem estar logados como admin (ex.: testes manuais via curl/Postman) param de funcionar** → Mitigação: é o comportamento correto e intencional desta correção; documentar no proposal/PR que chamadas diretas à API agora exigem Bearer token de um usuário com `role=admin`.
- **[Risco] Mudar a assinatura de `cleanup_vector_base` de `confirmation_phrase: str` para `dry_run: bool` é uma mudança de contrato interno** → Mitigação: é um método interno (`VectorAdminRepository`), não uma API pública; não há outros chamadores além de `VectorAdminService.cleanup`, confirmado por leitura de código.
- **[Trade-off] Calcular contagens de dry-run reaproveitando `list_files()` faz uma leitura completa da tabela `documents` mesmo em modo simulação** → aceitável: é exatamente o mesmo custo que `list_files()` já tem hoje no endpoint de listagem, e a base é pequena o suficiente para isso não ser um problema de performance neste estágio do produto.

## Migration Plan

1. Implementar os `Depends(...)` nas rotas de `main.py` e a correção de dry-run no service/repository (tasks detalhadas em `tasks.md`).
2. Testar localmente: (a) chamar cada endpoint `/admin/*` sem token → esperar 401; com token de usuário não-admin → esperar 403; com token de admin → esperar sucesso. (b) chamar `/consultoria/chat` sem token → 401; com qualquer token válido → sucesso. (c) chamar cleanup com `dry_run=true`/`confirmation_phrase="SIMULACAO"` e confirmar via `GET /admin/vector-base/files` que nada foi apagado; depois chamar com confirmação real e confirmar que os dados somem.
3. Deploy do backend. Não há migração de dados nem de schema — apenas mudança de código.
4. Rollback: reverter o commit/deploy do backend; nenhuma migração de banco a desfazer.

## Open Questions

- Nenhuma pendente para o escopo desta correção; itens fora de escopo (reindexação quebrada, CORS, dependências desatualizadas) ficam registrados na auditoria para mudanças futuras.
