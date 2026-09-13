## Context

Estado verificado no código e no banco:

- `rag_service.py:70-74`: `OpenAIEmbeddings(openai_api_key=..., http_client=..., http_async_client=...)` — **sem `model=`**, caindo no default `text-embedding-ada-002` (1536 dims).
- `rag_service.py:89-93`: `RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=500, separators=["\n\n", "\n", ". ", " ", ""])` — hardcoded.
- `rag_service.py:134`: `split_documents(cleaned_docs)` onde cada `Document` é **uma página** → o split reinicia a cada página.
- `rag_service.py:141-143`: apenas `original_file_id` e `original_file_name` são adicionados ao metadata. `chunk_index` não existe em lugar nenhum (0/49 no banco).
- Banco: 49 chunks, 4 arquivos, `vector_dims` = 1536 uniformes. Comprimento de conteúdo: mín 219 / médio 1900 / máx 3982 — a dispersão confirma o chunking por página (páginas curtas viram chunks curtos).
- Não existem colunas `page` nem `chunk_index` na tabela, embora `vector_admin_repository.py:108-112` as leia (sempre `None`).

Restrição incontornável: embeddings de modelos diferentes ocupam espaços vetoriais distintos. Não existe migração incremental — ou a base inteira é reindexada com o modelo novo, ou as similaridades ficam sem significado.

## Goals / Non-Goals

**Goals:**
- Recuperar chunks mais precisos para a mesma pergunta, comprovado por medição contra a linha de base.
- Tornar as escolhas de modelo e chunking **explícitas e versionadas**, para que uma regressão como a atual não possa acontecer em silêncio de novo.
- Habilitar rastreabilidade por chunk (posição e página), pré-requisito da citação de fontes.

**Non-Goals:**
- Não mexe em threshold, `k`, reranking, prompts ou montagem de contexto — isso é a mudança seguinte, e deliberadamente separada para que o efeito de cada uma seja medível isoladamente.
- Não implementa upload do PDF original para o Storage (fica para a mudança de robustez), embora a ausência disso seja o que torna esta mudança dependente de o usuário ter os arquivos.
- Não muda o OCR nem o parsing de PDF.

## Decisions

1. **`text-embedding-3-large` com `dimensions=1536`.** Os modelos v3 suportam redução de dimensão (Matryoshka), e o `3-large` truncado em 1536 supera tanto o `ada-002` quanto o `3-small` na mesma dimensionalidade. Escolhido por isso: **cabe no schema `vector(1536)` atual, sem migração de coluna nem de índice**, e ainda assim entrega a melhor qualidade de recuperação disponível. O custo adicional é irrelevante aqui — a base é minúscula e a query são ~20 tokens.
   - Alternativa considerada: `3-large` em 3072 dims nativos. Rejeitada por exigir `ALTER COLUMN` e recriação do índice HNSW em troca de ganho marginal neste acervo.
   - Alternativa considerada: `3-small`. Seria suficiente e mais barato, mas como o volume é irrisório, não há motivo para não pegar a qualidade melhor.

2. **`chunk_size=1200`, `chunk_overlap=200`.** Restaura a ordem de grandeza da versão que funcionava (1000/200), com folga para tabelas científicas que ficariam truncadas em 1000. A relação overlap/size (~17%) é conservadora e evita a redundância excessiva do 500/4000 atual.

3. **Ambos configuráveis por variável de ambiente, com o valor efetivo registrado em log na inicialização.** Esta é a decisão que impede a repetição do bug: hoje o serviço loga o `similarity_threshold` mas não o modelo de embedding nem o chunking, então a regressão passou despercebida por meses. O log de inicialização deve dizer qual modelo está em uso de fato.

4. **Chunking contínuo com rastreamento de página.** Concatenar as páginas do documento antes do split, mantendo um mapa de deslocamento → página, para atribuir a cada chunk a página inicial e final. Resolve o problema de conteúdo partido na quebra de página **sem** perder a rastreabilidade que a citação de fontes vai precisar.
   - Alternativa considerada: manter por página e apenas aumentar o overlap. Rejeitada — overlap não atravessa documentos distintos, que é exatamente o que cada página é hoje para o splitter.

5. **Metadados em JSONB e em colunas top-level.** O `vector_admin_repository` já lê `page` e `chunk_index` como colunas; o LangChain só escreve JSONB. Popular ambos resolve o descompasso sem reescrever o repositório. As colunas passam a existir de fato.

6. **A verificação é comparativa, não absoluta.** O critério de sucesso é a melhora das métricas de recuperação contra a linha de base registrada pela mudança `add-rag-evaluation-harness` — não uma impressão de que "as respostas parecem melhores".

## Risks / Trade-offs

- **[Risco] Reingestão é destrutiva e sem volta.** Limpar a base antes de reingerir significa que, se a reingestão falhar no meio, fica-se sem base. → Mitigação: confirmar que os 4 PDFs estão em mãos e legíveis **antes** de limpar; reingerir um documento e validar antes de processar os demais.
- **[Risco] `original_file_id = MD5(nome do arquivo)`** faz com que reingerir o mesmo nome seja bloqueado por `_check_file_exists`. Depois de limpar a base isso não bloqueia, mas se a limpeza for parcial, sim. → Mitigação: confirmar base zerada antes de reingerir. A correção definitiva (hash de conteúdo) está na mudança de robustez.
- **[Risco] Falha parcial de ingestão deixa o arquivo preso pela metade** (sem transação; `_check_file_exists` passa a dizer `already_exists`). → Mitigação: verificar a contagem de chunks por arquivo após cada ingestão; se divergir, excluir o arquivo pelo admin e reingerir.
- **[Risco] `clean_reindex_service.py` duplica os parâmetros de chunking e cria seu próprio cliente de embeddings sem o `http_client` do projeto** — se não for atualizado junto, reintroduz a divergência (e ignora a resolução de TLS do projeto). → Mitigação: tratá-lo explicitamente como parte desta mudança, não como detalhe.
- **[Trade-off] Chunks menores significam mais chunks e mais linhas** — mais chamadas de embedding na ingestão e um `k` que talvez precise subir para cobrir a mesma quantidade de texto. Aceito: é exatamente o trade-off que dá precisão. O ajuste de `k` fica para a mudança de recuperação, que é quem mede.
- **[Incerteza] O ganho não está garantido.** A hipótese de que chunk menor + modelo v3 melhora a recuperação é fortemente fundamentada, mas **precisa ser comprovada** neste acervo. Se a medição não mostrar melhora, a decisão deve ser revista em vez de racionalizada.

## Migration Plan

1. Implementar as mudanças de código (modelo, chunking, metadados) sem executar reingestão.
2. Adicionar as colunas de rastreabilidade no banco.
3. Confirmar que os 4 PDFs originais estão disponíveis.
4. Limpar a base vetorial (operação destrutiva, com confirmação explícita).
5. Reingerir os documentos um a um, validando a contagem de chunks a cada um.
6. Rodar o harness de avaliação e comparar com a linha de base.

Rollback: reverter o código por git e reingerir com a configuração anterior. Como os vetores são descartáveis e os originais estão preservados, o rollback é sempre possível — **desde que os PDFs originais continuem disponíveis**.

## Open Questions

- Chunks menores podem exigir aumentar o `k` de recuperação (hoje 20) para cobrir a mesma extensão de texto. A decisão fica para a mudança de recuperação, que tem a medição para fundamentá-la — mas convém observar o efeito já na verificação desta.

## Resultado da verificação (2026-08-01)

Implementação aplicada e base reingerida de ponta a ponta (4 documentos, dump de segurança antes de qualquer coisa destrutiva). Comparação feita de forma pareada, restrita às mesmas 19 perguntas `in_corpus` que existiam na linha de base (excluindo as 5 perguntas novas sobre o BIP 2024 adicionadas depois da linha de base, para não distorcer a média), e com `llm_expansion=False` dos dois lados — a linha de base tinha sido gravada sem expansão de query, e comparar com expansão ligada de um lado só teria sido uma segunda variável de confusão.

| Config | `mean_recall` (19 perguntas) | `mean_top_similarity` |
|---|---|---|
| Linha de base (`ada-002`, chunk 4000/500) | 0.895 | 0.847 |
| `chunk_size=1200` (proposto originalmente), `k=20` | 0.789 | 0.615 |
| `chunk_size=1600`, `k=20` | 0.842 | 0.606 |
| `chunk_size=1200`, `k=40` (teste isolado, só pra confirmar a causa) | **0.895** (idêntico à base) | 0.682 |

**Achado**: nem `chunk_size=1200` nem `1600` recuperam o recall da base mantendo `k=20` fixo. A causa foi isolada experimentalmente: aumentar só o `k` para 40 (sem tocar em chunk_size) faz o recall empatar exatamente com a linha de base. Isso confirma a suspeita já registrada nas "Open Questions" — chunks menores multiplicam o número de chunks por documento (ex.: BIP 2024 foi de 26 chunks com o `chunk_size` antigo para 78 com 1200, 57 com 1600), então a mesma janela `k=20` passa a cobrir uma fração menor do documento.

A queda de `mean_top_similarity` é consistente em praticamente todas as perguntas e provavelmente reflete recalibração de escala entre os dois modelos de embedding (é documentado que `ada-002` produz similaridades de cosseno artificialmente infladas; `text-embedding-3-large` é mais discriminativo mas com números absolutos menores para matches igualmente bons) — não necessariamente pior qualidade de correspondência semântica.

**Decisão final**: aceitar a mudança com `chunk_size=1600` (menor regressão de recall das duas opções testadas), registrando explicitamente que o ganho pretendido só se materializa por completo quando a mudança de recuperação ajustar `k` — decisão consciente do usuário, não uma falha silenciosa. `chunk_overlap` permanece 200. As demais entregas da mudança (config explícita e logada, chunking contínuo com rastreamento de página, colunas `page`/`chunk_index` populadas de fato, TLS corrigido em `clean_reindex_service.py`) foram verificadas e funcionam corretamente, independente do resultado do recall.

Checagem de ponta a ponta (`test_phase6_post_reindex_success_manual.py`): **✅ APROVADO**. Admin (`vector_admin_repository.get_file_chunks`) confirmado exibindo `page`/`chunk_index` reais e sequenciais por arquivo.
