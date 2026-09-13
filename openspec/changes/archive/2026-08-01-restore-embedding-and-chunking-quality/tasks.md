## 1. Pré-requisitos (antes de qualquer coisa destrutiva)

- [x] 1.1 Baseline do harness (`add-rag-evaluation-harness`) confirmada: `backend/evaluation/runs/20260727T055505Z-baseline-full-v2.json`, entre outras.
- [x] 1.2 Os 4 PDFs originais confirmados disponíveis e legíveis em `backend/docs/`: `Genetic and phenotypic characterization of Nile tilapia.pdf`, `BIP 2024 publicado.pdf`, `Indice volumetrico abate.pdf`, `BIA_RAG.pdf` (o `BIP 2024` foi localizado e fornecido pelo usuário nesta sessão — é uma versão diferente/melhor da que gerou o problema original documentado na change `fix-pdf-extraction-quality`, mas serve para os fins desta mudança).
- [x] 1.3 Dump de segurança do conteúdo antes de limpar (`SELECT * FROM documents`, 63 linhas, exceto a coluna `embedding`) salvo localmente antes da primeira limpeza.

## 2. Configuração explícita

- [x] 2.1 `EMBEDDING_MODEL` (default `text-embedding-3-large`), `EMBEDDING_DIMENSIONS` (`1536`), `CHUNK_SIZE` (`1600` — ver task 7.3/design.md, não 1200 como planejado inicialmente), `CHUNK_OVERLAP` (`200`) em `backend/.env.example`, com comentários explicando o porquê, incluindo o resultado real da comparação.
- [x] 2.2 Mesmas variáveis em `backend/.env`.
- [x] 2.3 `rag_service.py`: `model=`/`dimensions=` explícitos em `OpenAIEmbeddings`, lidos de `app.utils.rag_config`.
- [x] 2.4 `rag_service.py`: `chunk_size`/`chunk_overlap` do `RecursiveCharacterTextSplitter` lidos da mesma config.
- [x] 2.5 Log de inicialização estendido: `embedding_model`, `embedding_dimensions`, `chunk_size`, `chunk_overlap` e `similarity_threshold`, tudo numa linha só.

## 3. Chunking contínuo com rastreamento de página

- [x] 3.1 `app/utils/chunking.py` (novo): `split_pages_continuous` concatena o texto das páginas mantendo um mapa de offset → página.
- [x] 3.2 Split roda sobre o texto contínuo (`RecursiveCharacterTextSplitter.create_documents`, com `add_start_index=True` — resolve o rastreamento de offset sem reimplementar na mão); `page_start`/`page_end` derivados do mapa de offsets para cada chunk.
- [x] 3.3 Confirmado com teste sintético: um chunk que atravessa a quebra de página fica com `page_start != page_end` (ex.: `page_start=0, page_end=1`), provando que o overlap agora cruza a fronteira.
- [x] 3.4 Filtro de chunks curtos (`_filter_chunks`, <120 chars) mantido, agora rodando sobre a saída do chunking contínuo.

## 4. Metadados de rastreabilidade

- [x] 4.1 `chunk_index` (ordinal, atribuído **após** o filtro de curtos, sequencial sem lacunas) no metadata de cada chunk.
- [x] 4.2 `page_start`/`page_end` no metadata; `page` sempre setado (= `page_start`, inclusive quando o chunk atravessa página — decisão consciente, diferente da leitura literal original desta task, para não quebrar `_make_retrieval_dedup_key` que lê `metadata['page']` diretamente).
- [x] 4.3 Colunas `page integer` e `chunk_index integer` criadas em `public.documents` via `apply_migration` (projeto `tfdripphcwbjiveksuet`), confirmadas via `execute_sql`.
- [x] 4.4 Colunas top-level populadas de fato: **achado importante durante a implementação** — o `design.md` original presumia que isso já acontecia (backfill anterior, "49/49"), mas era um `UPDATE` manual único de uma change antiga, não um mecanismo vivo (só 37/63 linhas tinham essas colunas antes desta mudança). Implementado do zero: `RAGService._backfill_top_level_columns`, upsert em lote logo após `add_documents`, com checagem defensiva de tamanho (se `add_documents` não devolver a mesma quantidade de IDs dos splits, pula o backfill e loga erro — o JSONB permanece correto de qualquer forma).
- [x] 4.5 `original_file_id`/`original_file_name` confirmados 100% populados nas colunas top-level após a reingestão completa (173→124 linhas conforme o chunk_size final, 0 nulos).

## 5. Alinhar o caminho de reindexação

- [x] 5.1 `clean_reindex_service.py`: `default_chunk_size`/`default_chunk_overlap` agora vêm de `app.utils.rag_config` (mesma fonte de `rag_service.py`).
- [x] 5.2 `clean_reindex_service.py`: TLS corrigido — `httpx.Client(verify=_resolve_ssl_verify())` no `OpenAIEmbeddings`, mesmo padrão de `rag_service.py`. **Confirmado que este serviço está órfão** (nada em `main.py` o invoca com sucesso — `POST /admin/vector-base/reindex` chama métodos que não existem em `VectorAdminRepository`, levantaria `NotImplementedError`); a correção é higiene, não conserto de caminho ativo.
- [x] 5.3 Os três pontos que faziam `split_documents` agora chamam `split_pages_continuous` — os dois caminhos produzem chunks equivalentes por construção (mesma função compartilhada), não por verificação ad-hoc.

## 6. Reingestão (destrutivo)

- [x] 6.1 Base limpa via `vector_admin_repository.cleanup_vector_base("CONFIRMAR_LIMPEZA_TOTAL")` (confirmado explicitamente com o usuário antes de cada limpeza — houve duas, uma para testar `chunk_size=1200`, outra para `1600` após o resultado insatisfatório da primeira). Zerada e confirmada (`count(*) = 0`) antes de cada reingestão.
- [x] 6.2 Reingerido um documento por vez, validado a cada um: contagem de chunks, `chunk_index` sequencial sem lacunas, `page` preenchido, `vector_dims(embedding) = 1536` — confirmado nos 4 arquivos, nas duas rodadas (1200 e 1600).
- [x] 6.3 Todos os 4 reingeridos com sucesso nas duas rodadas.
- [x] 6.4 Confirmado ao final (config final, `chunk_size=1600`): 124 chunks, 0 sem embedding, 1 dimensão distinta (1536 uniforme), 0 linhas com `original_file_id`/`original_file_name`/`page`/`chunk_index` faltando.

## 7. Verificação

- [x] 7.1 Harness completo rodado e comparado com a linha de base — comparação pareada nas mesmas 19 perguntas `in_corpus` pré-existentes (excluindo as 5 novas do BIP 2024), com `llm_expansion=False` dos dois lados para eliminar uma segunda variável de confusão descoberta durante a verificação.
- [x] 7.2 Números registrados em `design.md` (seção "Resultado da verificação"), lado a lado com a linha de base.
- [x] 7.3 **Não houve melhora com `k=20` fixo em nenhum dos dois valores testados** (`chunk_size=1200`: recall 0.789; `1600`: recall 0.842; base: 0.895). Testado `1600` (não `800` — o diagnóstico já apontava que chunks menores pioram o problema, então testar 800 seria gasto sem hipótese a favor). **Decisão do usuário**: aceitar mesmo assim com `chunk_size=1600` (menor regressão), documentando a dependência de `k` para a próxima mudança em vez de reverter ou quebrar o escopo mexendo em `k` agora.
- [x] 7.4 Confirmado experimentalmente (não só "observado"): `k=40` com `chunk_size=1200` faz o `mean_recall` empatar exatamente com a linha de base (0.895 = 0.895) nas mesmas 19 perguntas — prova direta de que chunks menores exigem `k` maior para cobrir a mesma extensão de texto. Registrado para a mudança de recuperação decidir o valor final de `k`; não alterado aqui.
- [x] 7.5 `test_phase6_post_reindex_success_manual.py`: **✅ APROVADO** (docs recuperados, contexto ≥300 chars, termos de sucesso presentes, resposta não vazia).
- [x] 7.6 Admin confirmado: `vector_admin_repository.get_file_chunks` retorna `page`/`chunk_index` reais e sequenciais por arquivo (antes sempre `None`).
