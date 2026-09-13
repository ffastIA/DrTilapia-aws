## 1. Prompt único em prosa + sentinela de recusa (com evaluate reescrito no mesmo commit)

- [x] 1.1 Os 4 templates de `_build_system_prompt` substituídos por um prompt base único em prosa contínua, sem cabeçalhos de seção obrigatórios.
- [x] 1.2 `question_type` adiciona uma linha de ênfase ao prompt base (`_QUESTION_TYPE_EMPHASIS`: quantitative → precisão de valores/n/±/p; comparative → organizar contrastivamente; methodological → seguir ordem do experimento; conceptual → explicar conceito e relevância) em vez de selecionar um template inteiro.
- [x] 1.3 Removidos os exemplos com valores reais de um estudo específico (FIS 0.44/0.05, DEST 0.00-0.818, 7.05 vs 3.04, SAW/ILH).
- [x] 1.4 Regras de fundamentação preservadas e adaptadas para prosa (nomear populações/tratamentos individualmente, não extrapolar, preferir "o estudo encontrou X=Y").
- [x] 1.5 Instrução de recusa explícita adicionada: `NO_ANSWER_SENTINEL = "SEM_RESPOSTA_NO_CONTEXTO"`, instruída em todos os tipos de pergunta.
- [x] 1.6 `generate` detecta o sentinela e substitui por `_build_refusal_message(lang)` com `evaluation="REFUSED"` e `source_docs=[]`. Também aplicado ao caminho `insufficient_context` (que antes não zerava `source_docs` explicitamente). **Correção feita durante a task 7, com evidência ao vivo**: a detecção inicial usava `answer.strip() == NO_ANSWER_SENTINEL` (igualdade exata) — mas o modelo às vezes escreve uma explicação completa e só então acrescenta o sentinela no final, apesar da instrução pedir "exatamente X e nada mais" (observado em produção: `oos-dieta-restritiva`, resposta em prosa + sentinela ao fim, que passava como resposta válida citando 3 arquivos sem relação com a pergunta). Trocado para `NO_ANSWER_SENTINEL in answer` (substring). Isso sozinho levou `out_of_corpus_refusal_rate` de 0.273 para 0.636 no run completo (ver task 7).
- [x] 1.7 Implementado `looks_like_empty_skeleton(answer)` em `app/utils/answer_quality.py` (não em `rag_service.py` diretamente) — canônico, reusado tanto por `evaluate` (produção) quanto por `evaluation/metrics.py` (harness), para as duas medidas nunca divergirem. `_count_empty_sections`/`_data_section_has_numbers` removidos (dead code, sem outros chamadores).
- [x] 1.8 `evaluate` reescrito: sem string-matching por tipo; critério = não vazia + `_is_answer_relevant` + não `looks_like_empty_skeleton`.
- [x] 1.9 `effective_type` persistido no `State` por `generate` (retornado junto da resposta). Como não há mais checagem de cabeçalho por tipo, o descasamento question_type/effective_type deixou de ser possível por construção, não por `evaluate` ler o campo — mantido no `State` para observabilidade.
- [x] 1.10 `should_retry`: `retry_count < 1` (era `< 2`). Anotação de tipo corrigida para `Literal["retrieve_retry", "end"]`.
- [x] 1.11 16 testes em `tests/test_rag_answer_format.py`: prompt de nenhum tipo contém os marcadores antigos (`DATA:`, `COMPARISON:`, `EXPERIMENTAL DESIGN:`, `Empty section.`, `**Dados do Estudo:**` etc. — 16 marcadores checados); prompt instrui prosa contínua; sem os exemplos envenenados. Verificação empírica contra respostas reais fica na task 7 (medição completa).
- [x] 1.12 Testado: resposta igual ao sentinela (com e sem espaço em volta) → mensagem de recusa real, `sources=[]`. Resposta normal não é confundida com o sentinela.

**Verificado:** 16/16 testes em `test_rag_answer_format.py`, incluindo o teto de 1 retry (2 chamadas de geração no máximo, não 3) e a ressalva de confiança parcial (task 3).

## 2. Seleção de contexto por ranking com piso e teto

- [x] 2.1 Adicionadas a `rag_config.py`: `CONTEXT_MIN_CHUNKS=8`, `CONTEXT_MAX_CHUNKS=16`, `CONTEXT_CHAR_BUDGET=22000`, `CONTEXT_RELATIVE_MARGIN=0.08`, `CONTEXT_ABSOLUTE_FLOOR=0.45`, `CITATION_MAX_FILES=3` (adiantada da task 4.4, mesmo grupo de constantes), cada uma com comentário do número medido. `effective_config_summary()` estendida.
- [x] 2.2 Implementado `_select_context_docs(ranked) -> (docs, reason)`: recusa se `top < REFUSAL_FLOOR_SIMILARITY`; janela relativa; completa até `CONTEXT_MIN_CHUNKS`; corta em `CONTEXT_MAX_CHUNKS`; orçamento de caracteres sem cortar abaixo do mínimo.
- [x] 2.3 `_retrieve_docs_via_rpc`: o ramo `else` (não-`skip_threshold`) do regime binário foi substituído pela chamada a `_select_context_docs`. O ramo `skip_threshold=True` (usado por `retrieve_retry`) foi mantido intocado, por design (ver Non-Goals) — será substituído por `grade_context` na change `add-rag-self-correction-loop`.
- [x] 2.4 `deduped[:k]` removido do caminho não-`skip_threshold` — `_select_context_docs` já aplica seu próprio teto (`CONTEXT_MAX_CHUNKS`). Mantido no caminho `skip_threshold` (retry), que não é alterado nesta change.
- [x] 2.5 `REFUSAL_FLOOR_SIMILARITY` inalterado. `PRIMARY_RPC_SIMILARITY_THRESHOLD` (via `service.similarity_threshold`) passa a ser usado só pelo sinal de confiança da task 3, não mais como gate de seleção.
- [x] 2.6 7 testes unitários em `TestSelectContextDocs`: preenchimento mínimo (3 candidatos fortes + 20 distantes → 8 retornados via `min_fill`); orçamento com chunk de 30k chars → ainda ≥ mínimo; orçamento respeitado com pool abundante; muitos candidatos fortes → cortado em `CONTEXT_MAX_CHUNKS`; nenhum candidato no piso → vazio; pool vazio → vazio; candidato abaixo do piso absoluto ainda entra via preenchimento mínimo (não starva).
- [x] 2.7 `test_between_floor_and_threshold_keeps_all_candidates` reescrito como `test_between_floor_and_threshold_stays_within_selection_bounds` — 40 candidatos na zona intermediária, asserção `CONTEXT_MIN_CHUNKS ≤ len(docs) ≤ CONTEXT_MAX_CHUNKS` e `len(docs) < 40`.

**Verificado:** 19/19 testes em `test_rag_retrieval_refusal.py` passam (11 pré-existentes + 8 novos/reescritos deste grupo).

## 3. Sinal de confiança e ressalva

- [x] 3.1 `context_confidence ∈ {"strong", "partial"}` derivado no nó `retrieve` a partir de `top_similarity_raw` (via `trace_out` de `_retrieve_docs_via_rpc`, capturado ANTES de companions/preenchimento mínimo — o que importa é a força do match original) comparado contra `self.similarity_threshold`; adicionado ao `State`.
- [x] 3.2 Em `generate`, `context_confidence == "partial"` acrescenta ao prompt uma instrução para abrir sinalizando a incerteza em linguagem natural e marcar partes inferidas.
- [x] 3.3 2 testes em `TestConfidenceCaveat`: similaridade entre piso e limiar → prompt de sistema contém a instrução de ressalva; similaridade acima do limiar → prompt não contém a instrução.

## 4. Citações precisas

- [x] 4.1 `_extract_source_doc_info`: cada chunk carrega `page_start`/`page_end` individuais (já era assim) + novo campo `companion` (bool), necessário para a task 4.3.
- [x] 4.2 `_build_sources` reescrito: agrupa por arquivo com **lista de páginas discretas** (`set` de todas as páginas em `range(page_start, page_end+1)` por chunk, não um min/max acumulado). Colapso em intervalo visual fica no frontend (task 4.6) — o backend expor a lista discreta já resolve o problema real (implicar páginas não usadas); a apresentação em faixa é preocupação de exibição.
- [x] 4.3 Chunks de companion excluídos das fontes via `has_genuine_chunk[file]`: um arquivo só aparece se tiver pelo menos um chunk com `companion=False`.
- [x] 4.4 Arquivos ordenados pela primeira aparição em `source_docs` (preserva a ordem de rank — companions são sempre appendados no fim de `docs`, nunca antes do chunk genuíno que os torna elegíveis); truncado em `CITATION_MAX_FILES=3` (constante adicionada na task 2.1).
- [x] 4.5 `frontend/hooks/useChat.ts`: `ChatSource` trocado de `page_start`/`page_end` para `pages: number[]`. (`frontend/types/rag-admin.ts` não estava envolvido — é o tipo de outra tela, listagem de admin, não citações de chat; corrigido do texto original da task.)
- [x] 4.6 `frontend/components/ChatMessage.tsx`: `formatSource` reescrito com `formatPageRanges` — colapsa páginas discretas contíguas em intervalos (`[2,3,4,8]` → `"3-5, 9"`, 1-indexed para exibição, mesma convenção anterior).
- [x] 4.7 10 testes em `tests/test_citations.py`: 2 chunks de 1 arquivo → páginas exatas `[3, 9]`, não `[3..9]`; chunk com `page_start≠page_end` → todas as páginas do intervalo; arquivo só-companion excluído; companion do arquivo já citado é incluído; sem nome de arquivo → ignorado; mais de `CITATION_MAX_FILES` → truncado na ordem de rank.

**Verificado:** `npx tsc --noEmit` no frontend não introduziu nenhum erro novo (mesmos erros pré-existentes de sessões anteriores, não relacionados a `ChatMessage.tsx`/`useChat.ts`). `main.py` não precisou de mudança — `sources` é repassado sem reformatação.

## 5. Modelo de geração separado do utilitário

- [x] 5.1 `GENERATION_MODEL` (default `gpt-4o`) e `UTILITY_MODEL` (default `gpt-4o-mini`) adicionados a `rag_config.py`, lidos de variável de ambiente.
- [x] 5.2 `RAGService.__init__` instancia `self.llm_generation` e `self.llm_utility`, ambos herdando a config de TLS/http_client existente. Log de inicialização estendido com os dois modelos.
- [x] 5.3 Confirmado por grep: todos os 4 call sites de `self.llm.invoke` migrados — `generate` (resposta final) → `llm_generation`; `_extract_text_via_vision` (Vision OCR), `_expand_query_with_llm`, `_condense_followup_question` → `llm_utility`. Nenhum `self.llm` bare restante em `rag_service.py`. Também corrigidos os consumidores externos que acessavam `service.llm` diretamente: `evaluation/run_eval.py` (`capture_config`, os dois juízes — usam `llm_utility`, consistente com serem tarefas de avaliação, não geração de resposta ao usuário) e `test_phase3_rag_manual.py` (script manual, não pytest).

## 6. Companions limitados

- [x] 6.1 `DATA_COMPANION_ENABLED` (default `True`) e `DATA_COMPANION_MAX_TOTAL=3` adicionados a `rag_config.py` (feito junto com a task 2.1, mesmo lote de constantes).
- [x] 6.2 `_add_data_companion_chunks` reescrito: candidatos de todos os arquivos elegíveis são reunidos num pool único, ordenado globalmente por densidade de dígitos, com teto `DATA_COMPANION_MAX_TOTAL` sobre o TOTAL (não garantido por arquivo). Elegibilidade restrita a arquivos com chunk nos 3 primeiros de `docs` (top-3 do ranking pós-seleção).
- [x] 6.3 Orçamento de caracteres já consumido por `docs` é calculado antes de buscar candidatos; cada companion só entra se couber no restante (`remaining_budget`), decrescido a cada adição.
- [x] 6.4 Confirmado na task 4 (citações): companions são excluídos das fontes a menos que o arquivo já esteja citado por um chunk de ranking genuíno.
- [x] 6.5 6 testes em `tests/test_data_companions.py`: teto total mesmo com 3 arquivos elegíveis oferecendo 5 candidatos cada (nunca mais que `DATA_COMPANION_MAX_TOTAL`, não até 5×3); arquivo fora do top-3 não gera nem consulta ao banco; candidato maior que o orçamento restante não é adicionado; flag desligada pula tudo sem tocar o banco; sem `original_file_id` elegível → docs inalterados; lista vazia → vazio.

## 7. Medição e verificação

- [x] 7.1 Rodado `python -m evaluation.run_eval --full --k 40 --label pos-fase-a-sentinel-fix` contra o baseline honesto `pre-fase-a` (gerado pela change `fix-rag-eval-harness-fidelity`, 35 perguntas incl. as 7 adversariais — não as 28 originais, número desatualizado na task original). **Achado no meio da medição, corrigido no mesmo commit**: a primeira passagem (`pos-fase-a`, descartada) expôs que a detecção do sentinela por igualdade exata deixava passar respostas onde o modelo escrevia uma explicação e só então acrescentava o sentinela — corrigido para substring (ver task 1.6). Números finais abaixo já refletem a correção.

  | métrica | pre-fase-a | pos-fase-a-sentinel-fix | Δ |
  |---|---|---|---|
  | mean_recall | 0.812 | **0.958** | +0.146 |
  | mean_selected_chunks | 19.9 | **9.3** | -10.6 (dentro de 8-16) |
  | starvation_rate | 0.455 | **0.0** | -0.455 |
  | p95_context_chars | 59624 | **21950** | -37674 (~2.7×) |
  | refusal_correct_rate | 0.743 | **0.886** | +0.143 |
  | out_of_corpus_refusal_rate | 0.182 | **0.636** | +0.454 |
  | mean_groundedness | 98.3 | 95.4 | -2.9 |
  | mean_answers_question | 75.6 | **83.4** | +7.8 |
  | mean_mention_coverage | 0.792 | 0.729 | -0.063 |
  | skeleton_rate | 0.212 | **0.0** | -0.212 |
  | citation_file_count_mean | 2.27 | 1.89 | -0.38 |
  | citation_precision | 0.753 | 0.667 | -0.086 |
  | custo/run (USD) | 0.0955 | 0.4454 | +0.35 (modelo de geração mais forte) |

  As duas quedas (`mention_coverage`, `citation_precision`) foram inspecionadas caso a caso: majoritariamente artefatos de medição já conhecidos (notação `10^6` em vez de `10⁶`/`106` não normalizada; um caso — `gen-fis-extremos` — onde a resposta nova é mais completa/correta que o `must_mention` desatualizado do golden set, que cita ILH 0,05 como mínimo quando a tabela real tem DNC 0,01) e alguns casos legítimos de resposta mais cautelosa (hedged) em zona de confiança parcial citando mais de um arquivo. Nenhum caso inspecionado envolveu dado inventado.

- [x] 7.2 Confirmado integralmente: `starvation_rate` 0.455→**0.0**, `skeleton_rate` 0.212→**0.0** (as duas métricas que capturam exatamente o sintoma relatado), `mean_selected_chunks`=9.3, dentro do intervalo 8-16 alvo.
- [x] 7.3 Confirmado contra o baseline real (`pre-fase-a`=0.182, não os 0.75 desatualizados da task original, que vinham de um golden set sem os negativos adversariais): `out_of_corpus_refusal_rate` **melhorou** para 0.636, não regrediu.
- [x] 7.4 Verificado via o run completo (mesma pergunta do golden set, `oos-dieta-restritiva`): **parcialmente atingido, gap conhecido e documentado**. A resposta não inventa nem afirma nada falso — abre dizendo explicitamente que os documentos não abordam o tema — mas nem sempre aciona o sentinela/recusa estruturada (`sources=[]`); em ~50% das tentativas (observado em 3 chamadas reais nesta sessão) o modelo produz uma resposta em prosa hedged em vez de usar o sentinela, ainda citando 1-2 arquivos sem relação direta com a pergunta. Isso é uma limitação de o modelo nem sempre seguir "responda EXATAMENTE X" à risca — não um defeito na detecção (que já usa substring, não igualdade exata). É exatamente o tipo de caso que `grade_context` (julgamento semântico pré-geração, `add-rag-self-correction-loop`) resolve de forma confiável, ao decidir suficiência de contexto ANTES de gerar, em vez de depender de o modelo se autopolicidar via convenção textual.
- [x] 7.5 Verificado via o run completo: "Qual tratamento teve o maior e o menor RPL no BIP 2024?" (`bip-rpl-extremos`) → resposta em prosa correta ("PRO+MOS... 64,10%... MOS... 21,02%"), citando **só** `BIP 2024 publicado.pdf` — critério pleno.

**Backend/frontend confirmados rodando localmente** (`:8000`/`:3000`, ambos HTTP 200) durante a verificação; `uvicorn --reload` já ativo desde sessão anterior, recarregou o código automaticamente a cada edição.
