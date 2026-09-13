## Context

Estado verificado ao vivo em `tfdripphcwbjiveksuet` durante a revisão do RAG:

```
CREATE INDEX documents_vector_hnsw_idx ON public.documents
  USING hnsw (vector vector_cosine_ops) WITH (m='16', ef_construction='64')
```

Contagens sobre 49 linhas: `vector` = **0** preenchidas, `embedding` = **49** preenchidas (todas `vector_dims` = 1536, nenhuma nula). `pg_stat_user_indexes.idx_scan` do índice = 0; `documents.seq_scan` = 61.

`rpc_vector_search` consulta exclusivamente `embedding`:
```sql
SELECT d.id::text, d.content, d.metadata,
       1.0 - (d.embedding <=> query_embedding) AS similarity
FROM public.documents d
WHERE d.deleted_at IS NULL AND d.embedding IS NOT NULL
ORDER BY d.embedding <=> query_embedding ASC
LIMIT limit_count;
```

`insert_vector_batch` grava nas duas colunas (`VALUES (..., v, v)`) — mas as 49 linhas atuais **não vieram dela** (senão `vector` estaria preenchida). Foram escritas pelo `SupabaseVectorStore` do LangChain, que grava apenas `id`, `content`, `embedding`, `metadata`. Nenhum código Python referencia `insert_vector_batch`: é uma função órfã.

`to_regclass('public.ingestion_logs')` retorna `NULL` — a tabela nunca existiu. `vector_admin_repository.py:298-324` a consulta e sempre cai no `except`, logando warning a cada chamada e reportando `0`.

## Goals / Non-Goals

**Goals:**
- Busca vetorial usando índice, comprovadamente (não por inspeção visual do DDL, mas por `idx_scan` e plano de execução).
- Uma única fonte de verdade para o embedding — eliminar a ambiguidade de duas colunas.
- Fechar os alertas dos advisors de segurança e performance que incidem sobre o caminho do RAG.
- Remover código que finge funcionar (contadores de log que são sempre zero por exceção engolida).

**Non-Goals:**
- Não mexe em modelo de embedding, chunking, threshold, recuperação ou prompts.
- Não exige reingestão — os 49 vetores atuais continuam válidos.
- Não resolve a ausência de `page`/`chunk_index` como colunas; isso pertence à mudança de qualidade de ingestão, que é quem passará a populá-las.

## Decisions

1. **Índice sobre `embedding`, não migrar dados para `vector`.** As duas alternativas eram: mover os dados para `vector` (que já tem índice) ou indexar `embedding`. Escolhido indexar `embedding` porque é a coluna que todo o código — RPC de busca e LangChain — realmente usa; mover dados exigiria mudar a RPC e o vectorstore, com muito mais superfície de risco para nenhum benefício.

2. **Remover a coluna `vector` em vez de mantê-la vazia.** Manter uma coluna `vector(1536)` sempre nula é um convite a repetir exatamente este bug. Como está 0/49 e nada a lê, a remoção é segura. `insert_vector_batch` é ajustada junto.

3. **Preservar os parâmetros HNSW existentes (`m=16, ef_construction=64`).** São os defaults do pgvector e adequados para o volume atual; mudá-los agora seria otimização sem medição. Fica registrado que, quando a base crescer, `ef_search` em tempo de consulta é o parâmetro a calibrar.

4. **`CREATE INDEX CONCURRENTLY`** para não bloquear escritas durante a criação. Com 49 linhas é instantâneo de qualquer forma, mas o comando fica correto para quando a base for maior — é o tipo de detalhe que ninguém volta para corrigir depois.

5. **Remover o código de `ingestion_logs` em vez de criar a tabela.** Nada depende dessa informação; criar a tabela seria adicionar manutenção para um recurso que ninguém pediu. Os campos correspondentes saem também das respostas da API — expor um contador que é sempre zero é pior que não expor.

6. **Consolidar as políticas RLS duplicadas e usar `(select auth.role())`.** As políticas `Enable read for service_role` e `service_role can read documents` são redundantes e ambas executam por linha. O advisor `auth_rls_initplan` aponta que `auth.role()` sem subquery é reavaliado a cada linha — com o índice funcionando e a base crescendo, isso passa a importar.

## Risks / Trade-offs

- **[Risco] Remover uma coluna é irreversível.** → Mitigação: confirmar imediatamente antes da remoção que `count(vector)` ainda é 0 (não confiar na medição desta revisão), e executar em passo separado do resto.
- **[Risco] Alterar as políticas RLS pode quebrar o acesso do backend.** → Mitigação: a aplicação acessa `documents` com a chave `service_role`/secret, que é exatamente o que as políticas liberam; testar uma consulta real logo após a mudança, antes de considerar concluída.
- **[Risco] Ajustar `insert_vector_batch` sem que nada a chame** dá falsa sensação de teste. → Mitigação: registrar explicitamente que a função permanece órfã e que a verificação é por leitura do DDL, não por execução — ou remover a função por completo, o que também é defensável.
- **[Trade-off] Remover campos da API** (`ingestion_logs_deleted`) é uma quebra de contrato para consumidores. Aceito porque o valor era constante e falso; um consumidor que dependesse dele já estava sendo enganado.
- **[Observação] O ganho de performance não será mensurável agora.** Com 49 linhas, um `Seq Scan` é mais rápido que um `Index Scan`. A verificação precisa ser estrutural (o plano usa o índice quando o planejador o considera vantajoso) e não cronométrica — inclusive é possível que o planejador continue preferindo `Seq Scan` neste volume, o que **não** significa falha.

## Migration Plan

Mudanças de esquema em passos independentes e verificáveis, cada um confirmado antes do seguinte:
1. Criar o índice novo sobre `embedding` (aditivo, reversível).
2. Remover o índice antigo sobre `vector`.
3. Ajustar `insert_vector_batch`; remover a coluna `vector`.
4. `search_path` nas RPCs.
5. Consolidar políticas RLS.
6. Remover o código de `ingestion_logs` na aplicação.

Rollback: os passos 1-2 e 4-5 são reversíveis por DDL inverso. O passo 3 (remoção da coluna) é o único irreversível, e é seguro porque a coluna está vazia. O passo 6 é reversível por git.

## Open Questions

- `insert_vector_batch` deve ser corrigida ou removida? É órfã e a ingestão real usa o LangChain. Proposta: corrigir agora (menor risco) e avaliar a remoção quando a mudança de ingestão definir se passará a usá-la.
