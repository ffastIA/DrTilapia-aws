## Context

Pipeline atual (`_build_graph`, `rag_service.py:830-1166`): `retrieve` →
`grade_context` → (condicional: `reformulate_and_retrieve` se
`insufficient`, senão direto) → `generate` → `verify_numeric` → `evaluate` →
END.

`retrieve` chama `_retrieve_docs_via_rpc` (1925-2037), que hoje:
1. Expande a pergunta original com sinônimos via LLM em **uma única string**
   (`_expand_query_with_llm`, 1568-1599 — um bloco "4-6 sinônimos científicos
   e equivalentes bilíngues" apendado ao texto original).
2. Embute essa string uma vez (`_embed_query`) e faz uma única busca vetorial
   (`_search_rpc`, cosseno via `rpc_vector_search`).
3. `_select_context_docs` (2039-2105) calcula `top` = maior cosseno bruto
   entre os candidatos vetoriais e recusa (`[]`, `"refused"`) se `top <
   REFUSAL_FLOOR_SIMILARITY` (0.53, `rag_config.py:42-49`, calibrado contra a
   distribuição real do golden set: pergunta respondível mais fraca = 0.539,
   pergunta fora do escopo mais próxima = 0.512).
4. Quando isso acontece, `grade_context` (895-898) **curto-circuita para
   `"insufficient"` sem chamar `_grade_context_verdict`** — o juiz LLM
   estrito (SUFFICIENT/PARTIAL/INSUFFICIENT, 1455-1479, especificamente
   afinado para separar "mesmo assunto" de "assunto diferente parecido")
   nunca avalia essas perguntas.
5. A única retentativa (`reformulate_and_retrieve` → `_expand_query_for_retry`,
   1688-1699) é puramente baseada em regras (meia dúzia de pares PT/EN
   fixos: tilápia↔Oreochromis niloticus, restrição alimentar↔feed
   restriction, metabolismo↔metabolism), deliberadamente sem LLM ("evita uma
   dupla chamada", comentário 1105-1106), e passa pelo mesmo piso.

Consequência: uma pergunta legítima mas fraseada fora dessas ~6 regras fixas,
e cuja formulação original não cruza o piso de cosseno, nunca chega a ser
julgada semanticamente. O gargalo não é o juiz LLM (que já é bom em separar
relevante de "parecido mas errado") — é que ele só recebe **uma chance**,
definida por uma única formulação embutida da pergunta.

## Goals / Non-Goals

**Goals:**
- Dar a perguntas fraseadas de forma imprecisa/coloquial mais chances de
  cruzar o piso de recusa com a formulação certa, sem alterar nenhum limiar
  já calibrado (`REFUSAL_FLOOR_SIMILARITY`, `CONTEXT_ABSOLUTE_FLOOR`,
  `CONTEXT_RELATIVE_MARGIN`, `CONTEXT_MIN_CHUNKS`, `CONTEXT_MAX_CHUNKS`).
- Preservar o juiz LLM de `grade_context` como a barreira de precisão —
  mais variantes só devem significar mais perguntas chegando até ele, não
  um novo caminho que o contorna.
- Medir o efeito real (recall em perguntas coloquiais, `out_of_corpus_refusal_rate`,
  `citation_precision`) via o harness existente antes de mudar qualquer
  default de produção — mesmo padrão de `add-hybrid-lexical-vector-search`.

**Non-Goals:**
- Não mexer em `reformulate_and_retrieve`/`_expand_query_for_retry` (retry
  continua baseado em regras, como rede de segurança de baixo custo).
- Não mexer na busca híbrida léxica (`_rrf_fuse`, `HYBRID_SEARCH_ENABLED`) —
  ortogonal a este problema (ela ataca recall de termo exato/sigla, não
  tolerância a paráfrase).
- Não recalibrar nenhum limiar existente.
- Não paralelizar as chamadas de embedding/RPC nesta iteração (ver Riscos).

## Decisions

**1. Fusão por máxima similaridade de cosseno, não RRF.**
Todas as variantes usam o mesmo espaço de embedding (`text-embedding-3-large`)
e a mesma busca RPC — diferente da fusão léxico+vetorial, que usa RRF
justamente porque cosseno e `ts_rank_cd` são escalas incompatíveis
(`_rrf_fuse`, comentário 1758-1762). Aqui, manter o cosseno bruto (tomando o
máximo por chunk entre variantes) preserva exatamente a calibração existente
de `_select_context_docs` sem precisar de nenhuma normalização nova.
Alternativa descartada: rankear por RRF entre variantes — desnecessário e
perderia a escala calibrada em cosseno que todo o gate de recusa depende.

**2. Três variantes, geradas por duas chamadas LLM dedicadas (revisado
durante a validação).**
(1) pergunta original, (2) expansão por sinônimos já existente — reaproveita
`_expand_query_with_llm` tal como está, sem modificação —, (3) paráfrase em
registro técnico/científico, gerada por uma nova chamada dedicada
(`_generate_technical_paraphrase`). O design inicial pedia as 3 variantes
numa única chamada combinada, para economizar uma chamada de LLM utilitário
(mesma preocupação de custo documentada no retry, 1105-1106). **Medido na
validação**: essa chamada combinada produzia uma lista de sinônimos de
qualidade/variância pior que a chamada dedicada já usada em produção — a
ponto de o MÁXIMO de similaridade entre as variantes separadas ficar ABAIXO
do que a chamada única de hoje já alcançava sozinha em pelo menos um caso
real (`col-gen-fis-extremos`: 0.610 → 0.524, ver `tasks.md` §5.4). Corrigido
reaproveitando `_expand_query_with_llm` sem alteração como uma das variantes
— isso garante que o fan-out nunca fica pior que o comportamento de query
única de hoje, só adiciona chance. Custo: 2 chamadas utilitárias
(`gpt-4o-mini`, baratas) em vez de 1 — aceito, pois elimina uma classe de
regressão que uma única chamada combinada não conseguia evitar de forma
confiável. `MULTI_QUERY_VARIANT_COUNT` é env-configurável (default 3), mesmo
padrão de `RETRIEVAL_K`.

**3. `_select_context_docs` e o gate de recusa permanecem intocados.**
A função só lê `metadata["similarity"]` e `"lexical_rank" not in metadata`
(2066-2069, 2082). Desde que cada `Document` fundido carregue a maior
similaridade entre variantes e nenhum carregue `lexical_rank`, a função
funciona sem nenhuma alteração — o merge é um drop-in antes dela.

**4. Flag `MULTI_QUERY_EXPANSION_ENABLED`, default `false`.**
Mesmo padrão de rollout gradual de `HYBRID_SEARCH_ENABLED`
(`rag_config.py:112-116): implementar, validar pelo harness, só então
considerar mudar o default. Quando desligada, `_retrieve_docs_via_rpc` segue
o caminho de código exatamente igual ao atual (zero mudança de
comportamento).

**5. Retry (`reformulate_and_retrieve`) não muda.**
Com a 1ª tentativa mais robusta, a retentativa deve ser acionada com menos
frequência — essa fração (perguntas que ainda caem em
`reformulate_and_retrieve`) é uma métrica secundária a observar no harness,
não um motivo para mexer no retry agora. Se o retry continuar sendo
insuficiente após esta change, é uma decisão para uma iteração futura, com
dados.

## Riscos / Trade-offs

- **[Risco] Mais variantes aumentam a chance de uma pergunta fora do escopo
  cruzar o piso por acidente** → Mitigação: o juiz LLM de `grade_context`
  continua rodando sempre que `insufficient_context=False`, e é
  especificamente desenhado para pegar "mesmo vocabulário, assunto
  diferente". Validar com `run_grade_context_calibration.py` focado no
  conjunto `oos-*` (especialmente `oos-fis-carpa`, `oos-rpl-streptococcus`,
  os dois adversariais mais difíceis) antes de rodar o harness completo.
  Critério de aceite: `out_of_corpus_refusal_rate` deve continuar ~1.0.

- **[Risco] Prompt da paráfrase técnica adiciona fatos ou muda de assunto**
  → Mitigação: instrução explícita de "não adicionar fatos novos, não
  responder à pergunta", mesmo rigor das regras de grounding do prompt de
  geração (`_build_system_prompt`, 1531-1535). Checar manualmente 5-10
  saídas do prompt antes de rodar o harness em escala.

- **[Risco] Mais candidatos vetoriais por pergunta podem diluir
  `citation_precision`** (foi exatamente o que reprovou a busca híbrida:
  0.701→0.424) → Mitigação: `_select_context_docs` (teto de chunks, janela
  relativa) permanece inalterado, então o efeito esperado é menor que o da
  busca híbrida (que injetava candidatos de uma fonte ortogonal, léxica).
  Ainda assim, medir `citation_precision` e `mean_selected_chunks` no
  `--full` antes de considerar ligar o default.

- **[Risco confirmado na validação] Conteúdo tabular denso não se beneficia
  de paráfrase semântica** → Medido: `col-gen-fis-extremos` regrediu de
  recall 1.0 (baseline) para 0.0 (multi-query) porque o chunk-alvo é uma
  tabela numérica terse ("SAW 9.6 (1.08) 2 (0.32) ..."), que não casa bem
  por cosseno com uma paráfrase em prosa fluente, mesmo em registro técnico
  — mesmo motivo, já documentado neste projeto, pelo qual
  `add-hybrid-lexical-vector-search` existe (busca léxica/termo exato) e
  `_add_data_companion_chunks` existe (companions específicos de tabela).
  Fan-out semântico não resolve esse caso; não é o problema que esta change
  ataca. Mitigação: nenhuma nesta iteração — é um gap conhecido e ortogonal,
  candidato a ligar `MULTI_QUERY_EXPANSION_ENABLED` junto com
  `HYBRID_SEARCH_ENABLED` numa iteração futura (ver `tasks.md` §6.1).

- **[Risco/custo] N embeddings + N buscas RPC por pergunta na 1ª tentativa**
  → Mitigação: chamadas baratas (embedding + Postgres RPC), não a geração
  cara (`gpt-4o`, já é o item dominante de custo por pergunta desde
  `restore-rag-answer-quality`). `estimate_embedding_calls` do harness é
  atualizado para reportar o custo real, não assumido.

- **[Risco] Latência: chamadas hoje sequenciais** → Aceito nesta iteração
  (flag desligada por padrão, não afeta produção ainda). Se o harness
  aprovar o ganho de qualidade, avaliar paralelizar antes de considerar
  ligar o default em produção — registrado como questão em aberto, não
  bloqueia esta change.

## Migration Plan

Puramente aditivo — nova flag (default `false`), novo método, extensão de
`trace_out`. Sem migração de schema, sem reingestão. Rollback trivial:
reverter a flag para `false` (ou não setar a env var) volta ao comportamento
atual sem nenhuma outra mudança de estado. Sequência:
1. Implementar com a flag desligada, confirmar zero regressão no harness.
2. Adicionar perguntas `col-*` ao golden set, medir baseline.
3. Ligar a flag via env var (não o default) e medir com o harness
   (`--retrieval-only` primeiro, depois `--full`).
4. Só considerar mudar o default para `true` se: recall/`top_similarity`
   melhorar nas perguntas `col-*`, `out_of_corpus_refusal_rate` continuar
   ~1.0, e `citation_precision` não cair mais que 10-15% (mesma régua da
   busca híbrida).
5. Se regredir, manter o default `false`, documentar o trade-off real em
   `tasks.md` com números — mesmo precedente honesto de
   `add-hybrid-lexical-vector-search`.

## Open Questions

- `MULTI_QUERY_VARIANT_COUNT=3` é um ponto de partida razoável — vale
  revisitar (2 vs. 3 vs. mais) se o harness mostrar que uma variante em
  particular (ex.: a paráfrase técnica) domina o ganho e as outras são
  redundantes.
- Paralelizar as N chamadas de embedding/busca fica para uma iteração
  futura, condicionada a esta change ser aprovada pelo harness primeiro.
