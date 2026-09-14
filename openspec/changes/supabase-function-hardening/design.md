## Context

Esta mudança é inteiramente do lado do banco (Supabase/Postgres), não do código da aplicação. A fonte dos achados é `docs/auditoria-fullstack.md`, seção M2, que por sua vez cita os *advisors* de segurança/performance do Supabase (ferramenta de lint nativa do projeto, acessível via dashboard ou CLI). Diferente dos itens C1-C5 do mesmo relatório — que descreviam código deste repositório e cuja leitura direta nesta sessão mostrou já estarem corrigidos —, os itens M2 descrevem configuração do banco em si, que não é observável lendo o código-fonte.

## Goals / Non-Goals

**Goals:**
- Nenhuma função `SECURITY DEFINER` de uso interno/administrativo é executável por papéis `anon`/`authenticated` sem necessidade.
- Funções usadas pelo pipeline RAG (`insert_vector_batch`, `rpc_vector_search`) têm `search_path` fixado.
- Proteção de senha vazada habilitada no Auth.

**Non-Goals:**
- Mover a extensão `vector` de schema é tratado como avaliação separada, não uma ação obrigatória desta mudança — o risco de quebrar índices/tipos dependentes é maior que o dos outros itens, que são de baixo risco.
- Não reavaliar todas as demais funções do banco além das citadas — escopo limitado ao que o relatório de auditoria já identificou.

## Decisions

1. **Reverificar antes de aplicar**: como o mesmo relatório continha achados C1-C5 já desatualizados (código já corrigido), a hipótese mais provável é que este relatório foi gerado num momento anterior do projeto e nem todo item necessariamente ainda reflete o estado atual do banco — mas, diferente do código (que pôde ser lido diretamente nesta sessão), o estado do banco não pôde ser reverificado nesta sessão por falta de acesso a uma ferramenta de advisors/CLI do Supabase. Por isso, a primeira tarefa desta mudança é *rodar os advisors de segurança novamente* antes de qualquer alteração.
2. **SQL versionado, não só dashboard**: preferir aplicar via um arquivo de migration versionado no repositório (se existir uma convenção de migrations do projeto) para que a mudança fique auditável e reproduzível entre ambientes (dev/prod) — evita que a correção exista só no projeto Supabase de produção sem rastro no controle de versão.
3. **Mover a extensão `vector` fica separado**: por ser potencialmente disruptivo (pode exigir recriar índices HNSW/IVFFlat existentes), esta ação é tratada como uma tarefa opcional/avaliação, não uma correção obrigatória no mesmo lote das outras três.

## Risks / Trade-offs

- **[Risco de dados desatualizados]** Esta proposta pode estar corrigindo problemas que já não existem (como aconteceu com C1-C5) — mitigado exigindo a reverificação ao vivo como primeira tarefa, antes de qualquer `ALTER FUNCTION`/`REVOKE`.
- **[Risco operacional]** Revogar `EXECUTE` de `rls_auto_enable()` pode quebrar algum fluxo que dependa dela via RPC pública — mitigado checando, antes de revogar, se há alguma chamada real a essa função a partir do frontend/backend (busca por `rls_auto_enable` no código da aplicação).
