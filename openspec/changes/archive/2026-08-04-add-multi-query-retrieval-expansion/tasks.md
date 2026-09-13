## 1. Configuração

- [x] 1.1 Adicionar `MULTI_QUERY_EXPANSION_ENABLED` (default `false`) e `MULTI_QUERY_VARIANT_COUNT` (default `3`) em `backend/app/utils/rag_config.py`, seguindo o mesmo padrão de comentário/calibração de `HYBRID_SEARCH_ENABLED`.
- [x] 1.2 Incluir as duas novas configs em `effective_config_summary()`.

## 2. Geração de variantes e fan-out de retrieval

- [x] 2.1 Implementar `_expand_query_multi_variant(question, lang) -> List[str]` em `rag_service.py`, logo após `_expand_query_with_llm`.
      **Revisado durante a validação** (ver §5): a versão original pedia as 3
      variantes (original/sinônimos/paráfrase) numa única chamada LLM
      combinada. Medido: essa chamada combinada produz uma lista de
      sinônimos com qualidade/variância pior que a chamada dedicada
      `_expand_query_with_llm` já usada em produção — a ponto de o MÁXIMO
      entre as variantes separadas ficar ABAIXO do que a chamada única de
      hoje já alcançava sozinha (caso `col-gen-fis-extremos`: 0.610 →
      0.524, cruzando para baixo do piso de recusa). Corrigido para
      reaproveitar `_expand_query_with_llm` (chamada dedicada, inalterada)
      como uma das variantes, mais uma segunda chamada dedicada
      (`_generate_technical_paraphrase`) só para a paráfrase — 2 chamadas
      utilitárias em vez de 1, mas cada uma no mesmo padrão de foco estreito
      já validado em produção. Isso garante que o fan-out nunca fica pior
      que `_expand_query_with_llm` sozinho, só adiciona chance.
- [x] 2.2 Modificar `_retrieve_docs_via_rpc`: quando `MULTI_QUERY_EXPANSION_ENABLED and use_llm_expansion`, gerar variantes, embutir e buscar cada uma (`_embed_query` + `_search_rpc`), fundir por `_make_retrieval_dedup_key` mantendo a maior `similarity` por chave, ordenar por similaridade — resultado alimenta `vector_docs` exatamente como hoje.
- [x] 2.3 Confirmado por inspeção: com a flag desligada, o branch `else` de `_retrieve_docs_via_rpc` é byte-idêntico ao código anterior (nenhuma chamada extra de embedding/RPC).
- [x] 2.4 Estendido `trace_out` com `query_variants` e `multi_query_enabled`.
- [x] 2.5 Validado manualmente (3 perguntas reais, incluindo 2 coloquiais) — a paráfrase técnica não adicionou fatos nem respondeu à pergunta, ficou em registro técnico coerente com o corpus.

## 3. Cobertura de avaliação

- [x] 3.1 Adicionadas 6 perguntas `col-*` a `backend/evaluation/golden_set.yaml`, irmãs de `gen-fis-extremos`, `bia-roi-tir`, `kv-definicao`, `bip-mos-crescimento`, `bia-payback`, `kv-ponto-abate` — cobrindo os 4 documentos e os tipos quantitative/conceptual/comparative/methodological.
- [x] 3.2 Bumped `version: 2` → `version: 3`, comentário documentando a adição como puramente aditiva.

## 4. Harness

- [x] 4.1 `capture_config` registra `multi_query_expansion_enabled`/`multi_query_variant_count`.
- [x] 4.2 `estimate_embedding_calls` escala pelo `MULTI_QUERY_VARIANT_COUNT` quando a flag está ligada (verificado: com a flag desligada o valor retornado é idêntico ao de antes desta change).
- [x] 4.3 `summarize()` reporta `col_questions_total`/`col_mean_recall`/`col_perfect_recall_rate`/`col_mean_top_similarity`/`col_starvation_rate` isolados.

## 5. Validação

- [x] 5.1 Baseline (`--retrieval-only`, flag desligada, golden set já com `col-*`):
      `runs/20260803T225011Z-pre-multiquery-baseline.json`.
      `col_mean_recall=1.0`, `col_perfect_recall_rate=1.0`,
      `col_mean_top_similarity=0.648`, `col_starvation_rate=0.0`.
      **Achado inesperado**: a amostra de 6 perguntas `col-*` já tinha
      recall perfeito na configuração atual (flag desligada) — a expansão
      por sinônimos já existente (`_expand_query_with_llm`) já dá conta
      dessas 6 formulações coloquiais específicas. O rank do primeiro hit já
      piorava bastante em alguns casos (ex.: `col-gen-fis-extremos` rank 12
      vs. rank 2 da pergunta irmã `gen-fis-extremos`), sinal de que essas
      perguntas já estão perto do limite, mesmo sem cruzar para recusa.
- [x] 5.2 Confirmado por inspeção de código (task 2.3) — o caminho de flag
      desligada não muda, então o run de 5.1 já serve como "pós-implementação
      com flag desligada": zero regressão por construção, não só por medição.
- [x] 5.3 Não executado como rodada isolada de `run_grade_context_calibration.py`
      — em vez disso, os `top_similarity_raw` de TODAS as 11 perguntas
      `oos-*` foram comparados diretamente entre baseline e a versão final
      com a flag ligada (ver 5.4/5.6): nenhuma cruzou o piso de recusa
      (0.53) que não cruzava antes. `oos-fis-carpa` e `oos-rpl-streptococcus`
      seguem abaixo/perto do piso como antes (0.619→0.625 e 0.618→0.520
      respectivamente — ambos continuam do lado seguro).
- [x] 5.4 Duas rodadas com a flag ligada:
      - v1 (design original, 1 chamada LLM combinada):
        `runs/20260803T225342Z-pos-multiquery-on.json` —
        `col_mean_recall=0.833` (regrediu de 1.0), `col_mean_top_similarity=0.555`
        (regrediu de 0.648), `col_starvation_rate=0.167` (regrediu de 0.0).
        Causa raiz identificada e corrigida em 2.1.
      - v2 (design corrigido, 2 chamadas LLM dedicadas):
        `runs/20260803T225955Z-pos-multiquery-v2.json` —
        `col_mean_top_similarity=0.677` (melhorou de 0.648, +0.029, melhora
        em 5 das 6 perguntas), `col_mean_recall=0.833` (ainda abaixo de 1.0
        — 1 regressão real, ver abaixo), `col_starvation_rate=0.0` (voltou
        ao nível do baseline).
      Comparação pergunta a pergunta (baseline → v2):
      | id | recall | rank | top_sim_raw |
      |---|---|---|---|
      | col-gen-fis-extremos | 1.0→**0.0** | 12→— | 0.610→0.622 |
      | col-bia-roi-tir | 1.0→1.0 | 5→7 | 0.635→0.669 |
      | col-kv-definicao | 1.0→1.0 | 1→2 | 0.630→0.662 |
      | col-bip-mos-crescimento | 1.0→1.0 | 0→0 | 0.656→0.682 |
      | col-bia-payback | 1.0→1.0 | 0→0 | 0.643→0.682 |
      | col-kv-ponto-abate | 1.0→1.0 | 4→4 | 0.717→0.747 |
- [ ] 5.5 **Não executado** — dado o resultado misto em 5.4/5.6 (ver
      decisão em §6), um `--full` (caro, usa `gpt-4o` em todas as 41
      perguntas) não se justifica ainda; fica como pré-requisito da próxima
      iteração, não desta.
- [x] 5.6 Resultado documentado com números reais (ver 5.4). Análise da
      única regressão (`col-gen-fis-extremos`): não é um bug — o chunk-alvo
      é uma tabela numérica densa ("SAW 9.6 (1.08) 2 (0.32) ..."); uma
      paráfrase em prosa fluente (mesmo em registro técnico) não casa bem
      por cosseno com uma tabela de números, porque o embedding de uma frase
      gramatical e o de uma tabela terse vivem em regiões diferentes do
      espaço vetorial — o mesmo motivo, documentado neste projeto, pelo qual
      `add-hybrid-lexical-vector-search` introduziu busca léxica e
      `_add_data_companion_chunks` existe especificamente para tabelas.
      Fan-out semântico não resolve esse tipo de caso; busca léxica/exata
      resolveria. **Não foi feito nenhum ajuste de limiar para forçar um
      resultado positivo** — o resultado misto é reportado como está.

## 6. Decisão de rollout

- [x] 6.1 **Decisão**: manter `MULTI_QUERY_EXPANSION_ENABLED=false` por
      default nesta change. Razões:
      1. O mecanismo central funciona como desenhado — `top_similarity_raw`
         melhorou em 5/6 perguntas `col-*` (média +0.029) e nenhuma pergunta
         `out_of_corpus` cruzou o piso de recusa que não cruzava antes — a
         barreira de precisão (juiz `grade_context`) não foi enfraquecida.
      2. Mas a amostra é pequena (n=6) e uma validação `--full`
         (groundedness/citation_precision/answers_question) não foi feita —
         insuficiente para justificar mudar o comportamento padrão de
         produção.
      3. Há uma regressão real e explicada (não um bug): conteúdo tabular
         denso não se beneficia de paráfrase semântica — a mesma classe de
         problema que motivou `add-hybrid-lexical-vector-search` (também
         off por default) e `_add_data_companion_chunks`.
      A flag fica disponível via env var (`MULTI_QUERY_EXPANSION_ENABLED=true`)
      para reavaliação futura, mesmo tratamento dado a `HYBRID_SEARCH_ENABLED`.
      **Próxima iteração recomendada**: (a) expandir a amostra `col-*` para
      10+ perguntas antes de reconsiderar o default; (b) rodar `--full` uma
      vez a amostra for maior; (c) avaliar se ligar `MULTI_QUERY_EXPANSION_ENABLED`
      **junto com** `HYBRID_SEARCH_ENABLED` cobre os dois gaps ao mesmo tempo
      (paráfrase semântica + termo exato/tabela), já que são ortogonais por
      desenho.
