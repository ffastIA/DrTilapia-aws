# Auditoria Fullstack DrTilápIA — Relatório de Segurança e Correções

## Contexto

Revisão da aplicação fullstack (FastAPI + Supabase + LangGraph + Next.js) contra as diretrizes `web-design-guidelines`, `supabase-postgres-best-practices`, `supabase` e uma revisão de código geral, procurando falhas de segurança, integrações quebradas e outras boas práticas.

Método: 4 agentes de exploração em paralelo (segurança backend; camada de serviços/RPC/storage; frontend/acessibilidade; inventário estrutural) + auditoria **ao vivo** do banco Supabase real (`tfdripphcwbjiveksuet`) via advisors de segurança/performance e leitura direta de RLS/policies/funções. Duas descobertas de maior severidade foram confirmadas lendo o código-fonte (`frontend/middleware.ts`, `backend/app/vector_admin_schemas.py`). Base do código auditada: HEAD `eaa71ca` (versão LangGraph/vídeo/imagem).

Este documento é somente um relatório — nenhuma correção foi aplicada. Serve de guia de insumo para abrir mudanças OpenSpec (`openspec new change ...`) que corrijam os itens listados, uma spec por item ou por grupo relacionado.

> **Nota sobre "webhooks":** não existe nenhum webhook no projeto (busca exaustiva por `webhook/hmac/signature/callback/edge function/pg_net` = 0 ocorrências no backend). Portanto não há assinatura a verificar. O que de fato está "quebrado" são **endpoints e integrações internas** (ver H3). Todo processamento pesado roda inline no request (não há fila/callback assíncrono).

---

## 🔴 CRÍTICO (segurança / perda de dados)

**C1. Verificação TLS globalmente desabilitada (`verify=False`)** — `backend/app/database.py:49-54` (todo tráfego Supabase, incluindo a chave `service_role`) e `backend/app/services/rag_service.py:64-66` (todo tráfego OpenAI, incluindo a API key). Incondicional, sem gate de ambiente. Segredos trafegam por canal sem verificação de certificado → vulnerável a MITM.
→ *Correção:* apontar `httpx` para o CA bundle do proxy corporativo (`verify="/caminho/ca.pem"` ou `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`); nunca embarcar `verify=False`; se inevitável em dev, gatear por env e jamais em produção.

**C2. Gate de admin no frontend confia em cookie gravável pelo cliente** — `frontend/middleware.ts:36-46` faz `JSON.parse(cookie 'user').role !== 'admin'`, e a regra 1 (`:24`) só checa **presença** do token, sem validar assinatura/`exp`. Qualquer um roda `document.cookie='user={"role":"admin"}'` e passa o gate. O backend ainda valida na API (limita vazamento de dados), mas a superfície de UI admin fica exposta.
→ *Correção:* validar o JWT no middleware (assinatura + `exp` via JWKS do Supabase) ou consultar o backend; nunca derivar autorização de cookie gravável pelo cliente.

**C3. Body vazio `{}` no cleanup = wipe destrutivo total** — `backend/app/vector_admin_schemas.py:54-63`: quando `confirmation_phrase` vem vazio e `dry_run` não é `True`, é reescrito para `CONFIRMAR_LIMPEZA_TOTAL`. Além disso `vector_admin_service.cleanup(False)` (`vector_admin_service.py:89-95`) sintetiza a frase. `POST /admin/vector-base/cleanup {}` apaga todos os documentos + storage. A checagem de confirmação no repositório (`vector_admin_repository.py:401-403`) é decorativa.
→ *Correção:* exigir a frase exata **enviada pelo chamador**; default = dry-run; remover a coerção `bool`→frase em `delete_file`/`cleanup`.

**C4. `service_role` usado em todas as requisições → RLS ignorada em todo o app** — `backend/app/database.py:56-57` (`supabase = supabase_admin`); `dependencies.py` e todos os serviços usam o cliente privilegiado. Isolamento por usuário existe só via `if` em Python (`fish_image_service.py:240`, `main.py:426/433`); `GET /videos` e `DELETE /videos/{id}` não têm **nenhuma** checagem de dono (retornam todos os vídeos + URL assinada de 24h a qualquer autenticado).
→ *Correção:* usar cliente com o JWT do usuário (RLS ativa) para dados de usuário; reservar `service_role` só para operações realmente privilegiadas; adicionar checagem de dono em vídeos.

**C5. Higiene de segredos** — `backend/.env`: `SECRET_KEY` é **idêntico** à `service_role`. `.env` raiz: `SUPABASE_KEY` é `service_role` (deveria ser `anon`), e contém `SUPABASE_DB_PASSWORD` + `SUPABASE_DATABASE_URL` (credenciais diretas de Postgres); `backend/docker-compose.yml:9-12` monta esse `.env` raiz no container. Os dois `.env` apontam para **projetos Supabase diferentes**. Além disso, a chave `service_role` foi colada em texto puro no chat nesta sessão.
→ *Correção:* **rotacionar as chaves `service_role` e `anon`** (a `service_role` foi exposta); corrigir `anon` vs `service_role`; remover `SECRET_KEY` duplicado; não montar credenciais de superusuário do banco no container da aplicação; consolidar em um único projeto/`.env`.

---

## 🟠 ALTO

**H1. Uploads sem limite de tamanho e content-type forjado do nome do arquivo** — `main.py:133/272/349` leem o corpo inteiro em memória (`await file.read()`), sem `MAX_SIZE`. `_content_type()` (`fish_image_service.py:45`, `video_service.py:84`) deriva o tipo da extensão do nome (nunca lê os bytes). O nome original é persistido verbatim e reexibido → superfície de XSS armazenado + DoS por memória/CPU (OCR/rembg sem limite de páginas/pixels).
→ *Correção:* limite de tamanho (streaming), validar magic bytes, sanitizar/escapar nome armazenado, cap de páginas/pixels.

**H2. IO bloqueante no event loop** — `supabase-py` e LangChain `.invoke()` são síncronos; só 2 dos 17 endpoints usam `to_thread`. `ingest_pdf` é `async` com **zero `await`** e faz OCR/Vision por página (bloqueia o servidor por minutos). `dependencies.py:24/32` faz **2 round-trips bloqueantes por request autenticado**.
→ *Correção:* `run_in_executor`/`to_thread` ou cliente async; mover ingestão pesada para worker em background.

**H3. Endpoints/integrações quebrados (o que "está quebrado")**
- `POST /admin/vector-base/reindex` → sempre **500** (repositório não tem método de reindex); o frontend chama (`ragAdminApi.ts:11`, `useRagAdmin.ts:143`).
- `GET /admin/vector-base/files/{id}/diagnosis` → sempre **500** (`vector_admin_service.py:73` procura `diagnose_file`; o método real é `diagnose_file_recovery`).
- `GET /admin/vector-base/files/{id}/content` → **200 vazio** (retorna chave `recovered_content`, schema espera `content` com `extra="ignore"`).
- `/consultoria/chat` → `sources` sempre `[]` (`main.py:111-112`); a spec exige atribuição de fonte.
- Exclusão de storage no admin vetorial é **código morto** (`vector_admin_repository.py:345-355` filtra colunas top-level sempre `NULL`); `has_storage`/diagnóstico sempre `False`.
- `clean_reindex_service` identifica arquivos por colunas `NULL` em 2 das 3 estratégias → **duplicação silenciosa de chunks** (hoje só via script, não exposto).
→ *Correção:* implementar reindex ou remover endpoint+UI; corrigir nome do método; alinhar chave do schema; popular `sources`; aplicar a mesma resolução por ID real usada em `delete_file` à exclusão de storage.

**H4. Vazamento de detalhes internos em erros** — `str(e)` retornado ao cliente em 13+ pontos de `main.py` (`:117,147,159,168,177,186,195,212,226,238,293,312,331` + fish `:369,392,409,564,586,603`), expondo nomes de tabela/coluna/constraint do PostgREST e erros SSL/hostnames internos. Ingestão retorna **200 mesmo em falha** (`rag_service.py:157`, `main.py:137-142`).
→ *Correção:* mensagem genérica ao cliente + log detalhado no servidor; status HTTP corretos.

**H5. Dependências com CVEs** — `python-multipart==0.0.9` (CVE-2024-53981, usado por todos os uploads; corrigido em 0.0.18); `python-jose[cryptography]==3.3.0` (CVE-2024-33663/33664; pinado mas não usado); `bcrypt==4.1.2` pinado e não importado.
→ *Correção:* subir `python-multipart≥0.0.18`, remover `python-jose` e `bcrypt` (ou atualizar se forem usar).

**H6. Robustez de autenticação** — JWT validado só remotamente (round-trip por request, sobre `verify=False`); exceções viram **500** em vez de 401 e sem log (`dependencies.py:50-52`); `/auth/login` sem rate limiting/lockout; `/docs`, `/redoc`, `/openapi.json` públicos (`app = FastAPI()`, `main.py:62`) expõem toda a superfície admin.
→ *Correção:* verificação local do JWT com JWKS + cache curto; mapear erros para 401; rate limiting no login; desabilitar/gatear docs em produção.

---

## 🟡 MÉDIO

**M1. Performance de RLS/índices (advisors ao vivo)** — `auth.<fn>()` não encapsulado em `(select …)` em ~19 policies (re-avaliação por linha); policies permissivas duplicadas em `documents` (`Enable read/insert…` vs `service_role can read/insert…`); FKs sem índice (`fish_analyses.user_id`, `fish_images.analysis_id`/`user_id`, `videos.uploaded_by`); índices não usados. → aplicar remediações do linter.

**M2. Hardening de funções/DB (advisors ao vivo)** — `public.rls_auto_enable()` é `SECURITY DEFINER` executável por `anon`/`authenticated` via `/rest/v1/rpc/` (revogar `EXECUTE`); `insert_vector_batch` e `rpc_vector_search` sem `SET search_path`; extensão `vector` no schema `public`; proteção contra senhas vazadas (HaveIBeenPwned) desabilitada no Auth.

**M3. Identidade de documentos e RAG** — `original_file_id = MD5(nome do arquivo)` (`rag_service.py:102`): nomes iguais colidem e bloqueiam re-ingestão; sem hash de conteúdo/versão. `PRIMARY_RPC_SIMILARITY_THRESHOLD` default **0.5** vs spec **0.7** (env não definido).

**M4. Consistência de storage/dados** — objeto órfão quando o `.insert()` **lança** (compensação só cobre `data` falsy: `video_service.py:150`, `fish_image_service.py:116`); N+1 de URLs assinadas nos endpoints de listagem; `SELECT *` sem paginação em `documents` (`vector_admin_repository.py:172`) → truncamento do PostgREST pode causar **delete/list parcial silencioso**.

**M5. Bugs que quebram o frontend em runtime** — `DocumentCard.tsx:3` importa `react-icons` (ausente do `package.json`) → quebra build/runtime; `useLoginMutation.mutate` ignora callbacks (`login/page.tsx:46`) → botão trava em "Entrando..." e redireciona para `/dashboard` inexistente; violação de Rules-of-Hooks (`admin/page.tsx:45-47`); `components/admin/page.tsx` órfão renderiza objeto em JSX; interceptor `api.ts:40` pode lançar em `config.url` indefinido e só trata 401 (não 403).

**M6. Duplicação/inconsistência de configuração** — dois `next.config` (`.js`/`.ts`), dois `globals.css` (Tailwind v3 vs v4), dois PostCSS; `providers.tsx` (React Query) nunca montado; classes Tailwind inexistentes (`text-text-secondary`, `bg-destructive`, `focus:ring-ring`) → banners de erro renderizam **sem estilo**.

---

## 🟢 BAIXO (acessibilidade e higiene)

**L1. Acessibilidade (Web Interface Guidelines)** — nenhum `focus-visible` em todo o código; `div`s clicáveis (dropzone `RagUploadPanel.tsx:139`, backdrops de modal); labels ausentes/não associados (várias telas de imagens/vídeos/RAG/chat); botões só-ícone sem `aria-label`; modais sem focus trap/`aria-modal`/Escape (exceto o órfão `ConfirmActionModal`); contraste baixo (`text-gray-500` em fundo escuro ≈3.7:1; branco sobre `accent #FFC107` ≈1.9:1); sem `aria-live` nos banners de status; `<video>` sem legendas.

**L2. Higiene de código** — caminho absoluto do Tesseract com o usuário (`rag_service.py:36-40`); scripts admin passam senha como argumento de CLI, `--role` sem allowlist, saem com código 0 em falha; imports duplicados e código morto (`vector_admin_repository.py`); `app/utils/` sem `__init__.py`; diretórios de upload vazios versionados; clientes `httpx` e handles do PyMuPDF não fechados (sem `try/finally`); OpenAI sem timeout/retry/cap de páginas (DoS de custo via Vision por página).

**L3. Logs** — `useChat.ts:38-48` faz `console.log` do tráfego de chat; backend loga o e-mail em todo login (INFO) e stack traces.

---

## Verificação (como este relatório foi validado)

- **Já feito nesta sessão:** advisors de segurança/performance do Supabase (via MCP `get_advisors`), leitura de `pg_policies`/`pg_class`/`pg_proc` (RLS, `rls_auto_enable`, `insert_vector_batch`), e leitura direta de `frontend/middleware.ts` e `backend/app/vector_admin_schemas.py` confirmando C2 e C3.
- **Reprodução pontual sugerida** (ao aplicar correções): `POST /admin/vector-base/cleanup` com body `{}` como admin em ambiente de teste (confirma C3); `GET /admin/vector-base/files/{id}/diagnosis` e `/reindex` retornando 500 (confirma H3); inspeção do `document.cookie` para C2.
- **Sem execução destrutiva** contra dados de produção durante esta auditoria.

## Próximo passo sugerido

Priorizar C1–C5 (segurança/perda de dados) e H3 (endpoints quebrados). Cada correção pode virar uma mudança OpenSpec revisável (`openspec new change ...`), coordenada com o outro ambiente de desenvolvimento paralelo para evitar conflito.
