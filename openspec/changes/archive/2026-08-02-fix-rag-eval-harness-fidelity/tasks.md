## 1. Seam de recuperação com histórico no serviço

- [x] 1.1 Adicionar em `RAGService` um método de suporte à avaliação que aplica `_condense_followup_question` seguido de `_retrieve_docs_via_rpc`, devolvendo `(docs, trace)`, onde `trace` inclui `candidate_count`, `top_similarity_raw` (antes de qualquer filtro), `selected_count`, `context_chars`, `selection_reason`. Implementado como `retrieve_for_eval`, usando um parâmetro `trace_out` opcional em `_retrieve_docs_via_rpc` (backward-compatible, nenhum chamador de produção precisa mudar).
- [x] 1.2 Documentar no docstring que este método existe para o harness de avaliação, não como API de produção; não expor via `main.py`.
- [x] 1.3 Teste unitário: chamar o método com uma pergunta de follow-up + histórico e confirmar que a query de busca usada é a condensada, não a pergunta crua. 4 testes em `TestRetrieveForEval` (condensação, sem histórico, trace pré-gate, contagem/chars).

## 2. Harness: retrieval com histórico

- [x] 2.1 `evaluate_retrieval` (`run_eval.py`) passa a chamar o seam de 1.1 em vez de `_retrieve_docs_via_rpc` diretamente, passando `question.get("history")`.
- [x] 2.2 Confirmar que perguntas sem histórico continuam avaliadas de forma idêntica a antes (query = pergunta literal) — `retrieve_for_eval` só condensa quando `history` é truthy, mesmo comportamento de `_condense_followup_question`.
- [x] 2.3 Re-rodado `--retrieval-only --k 40`: `fu-kv-por-que-importa` passou de `recall=0.0, retrieved_count=0` para `recall=1.00`. `fu-bip-rpl-menor` deixou de reportar `retrieved_count=0` (agora recupera 40 candidatos reais, `top_similarity=0.690`), mas continua com `recall=0.00` — a tabela de RPL do BIP 2024 não é recuperada nem para a pergunta original (`bip-rpl-extremos`, também `recall=0.00`), então esse resíduo é um problema real de recuperação, não mais um artefato de harness; fica para as changes seguintes do programa.

## 3. Captura de configuração completa

- [x] 3.1 `capture_config` passa a incluir `retrieval_k` e `use_llm_expansion`, além dos 6 campos já capturados. **Correção ao proposal**: esses dois valores já eram salvos no run (campos soltos `k`/`llm_expansion` no topo do JSON, lidos por `compare()`) — não eram inferidos de nome de arquivo. O defeito real era `config` (o dict) estar incompleto para esse propósito; corrigido sem descartar a filosofia original da função (ler dos objetos reais, não de constantes presumidas).
- [x] 3.2 Config completa persistida em todo modo de run — `capture_config` roda incondicionalmente em `main()`, antes só de `--full` ser diferente; confirmado com `--retrieval-only`.
- [x] 3.3 (não previsto originalmente, necessário pela mudança) `compare()` ajustado para não duplicar `k`/`retrieval_k` e `llm_expansion`/`use_llm_expansion` como linhas redundantes quando comparando um run antigo (sem os campos dentro de `config`) com um novo — fallback via `setdefault`, testado comparando um run de 2026-08-01 com um novo.

## 4. Normalização de métricas

- [x] 4.1 Em `metrics.py`, `normalize` trata vírgula e ponto como separador decimal equivalente (regex `(\d),(\d{1,2})\b` — só decimal de 1-2 casas, milhar tipo `17,000` não é tocado por não ter fronteira de palavra logo após 2 dígitos).
- [x] 4.2 Superscripts unicode (`⁰¹²³⁴⁵⁶⁷⁸⁹`) tratados como dígitos equivalentes via `str.translate`.
- [x] 4.3 Teste unitário em `tests/test_evaluation_metrics.py` cobrindo os casos reais do golden set: `64,10%` vs `64.10%`, `0,44` vs `0.44`, `R$ 17.000`/`12.280.000` (milhar, não tocado), `10⁸` vs `108`, mais `mention_coverage`/`passage_rank` ponta a ponta com os dois formatos.
- [x] 4.4 Confirmado via teste unitário direto (`test_mention_coverage_matches_across_decimal_formats`, `test_mention_coverage_matches_fis_values_across_formats`) que os casos de formatação decimal (RPL 64,10%/64.10%, FIS 0,44/0.44) agora pontuam corretamente — validação completa das 28 perguntas fica registrada no baseline da task 11.

## 5. `is_refusal` sem acoplamento a tamanho

- [x] 5.1 `is_refusal` reescrito para casar (substring, após normalização) contra `_build_refusal_message("pt-BR")`/`_build_refusal_message("en")` reais, via `get_rag_service()` (import local, não pesa o import do módulo para quem só precisa de `normalize`/`mention_coverage`).
- [x] 5.2 Removidos o corte `len < 400` **e também** o corte `len < 120` que a task original não mencionava explicitamente, mas que o spec (`Refusal detection is not coupled to answer length`) exige — nenhum corte de tamanho sobrevive; só a string vazia continua tratada como recusa (caso degenerado, não heurística de tamanho).
- [x] 5.3 Testes em `TestIsRefusalNotCoupledToLength`: mensagem de recusa real (pt/en) → recusa; a mesma mensagem com padding até ultrapassar 400 chars → ainda recusa; resposta curta e substantiva sem a mensagem → não é recusa; resposta vazia → recusa.

## 6. Juiz de groundedness contra o contexto real

- [x] 6.1 `AnswerResult` ganhou campo `debug: Optional[Dict[str, Any]] = None` (default `None`, não `{}` — evita dict mutável compartilhado entre instâncias); `get_answer` popula `debug={"context": result.get("context", "")}`. Não quebra nenhum chamador existente (todos usam kwargs/atributos, nenhum unpacking posicional).
- [x] 6.2 `build_judge` reescrito: `judge(question, answer, context)` recebe o contexto como parâmetro em vez de chamar `_retrieve_docs_via_rpc` internamente; `evaluate_generation` passa `answer_result.debug["context"]`.
- [x] 6.3 Verificado diretamente: `gen-fis-extremos` (resposta com todos os valores de FIS corretos) passou de `groundedness=0` (contexto re-recuperado pelo juiz não trazia a tabela) para `groundedness=100` (contexto real, que inclui o companion chunk com a tabela, julgado corretamente).

## 7. Novo juiz de utilidade

- [x] 7.1 Implementado `build_usefulness_judge`/`answers_question` (0-100): juiz vê **só pergunta e resposta**, sem contexto. **Calibração necessária não prevista na task original**: o primeiro prompt (instrução solta "responda de verdade... direta, específica e substantiva") pontuou uma resposta curta e correta com valor numérico concreto em só 20 — o juiz parecia penalizar concisão. Reescrito com âncoras explícitas de nota alta/baixa + exemplos; a mesma resposta passou a pontuar 90.
- [x] 7.2 Adicionado a `evaluate_generation` (parâmetro `usefulness_judge`, roda em toda resposta não recusada, dentro ou fora do escopo) e a `summarize` (`mean_answers_question`), sempre como campo separado de `groundedness`.
- [x] 7.3 Confirmado com o prompt calibrado: esqueleto vazio sintético → 10. Resposta real com valores corretos → 90, mesmo sendo curta.

## 8. Detecção de esqueleto vazio e métricas de contexto

- [x] 8.1 Implementado `looks_like_empty_skeleton(answer)` em `metrics.py` — conta ocorrências de marcadores de "sem dados/informação" (pt-BR + en); 2+ ocorrências (padrão multi-seção) ou 1 ocorrência numa resposta curta (<300 chars, provavelmente o conteúdo inteiro) marca como esqueleto. Não depende de cabeçalho de seção. 6 testes unitários, incluindo o caso de uma resposta longa e substantiva com uma única lacuna incidental (não deve ser marcada).
- [x] 8.2 `skeleton_rate` adicionado a `summarize` — fração das respostas NÃO recusadas que são esqueleto (uma recusa de verdade não é penalizada por conter os mesmos marcadores).
- [x] 8.3 `mean_selected_chunks`, `p95_context_chars`, `starvation_rate` adicionados a `summarize`, lidos do trace de `retrieve_for_eval` (presente em `entry["retrieval"]` em qualquer modo). `STARVATION_CHUNK_THRESHOLD=6` documentado como provisório — a change `restore-rag-answer-quality` formaliza como `CONTEXT_MIN_CHUNKS`. Smoke-testado: `mean_selected_chunks=16.1`, `starvation_rate=0.577` (confirma quantitativamente o diagnóstico — mais da metade das perguntas não recusadas recebe 6 chunks ou menos), `p95_context_chars=58706` (reflete os casos de inundação).

## 9. Precisão de citação

- [x] 9.1 `citation_file_count_mean` e `citation_precision` adicionados a `summarize`, computados só sobre respostas não recusadas. `citation_precision` por pergunta = fração dos arquivos citados que É o `expected_source_file` (uma resposta citando 3 arquivos com só 1 certo pontua 0.33, não some numa média binária "acertou/errou"); `None` quando não há arquivo esperado (out_of_corpus) ou nada foi citado.
- [x] 9.2 `cited_files`/`citation_file_count` registrados no detalhe por pergunta (`entry["generation"]`), tornando over-citação visível por pergunta, não só na média. Verificado ao vivo: `bip-rpl-extremos` cita só o BIP 2024 (`citation_precision=1.0`); `oos-doenca-estreptococose` — que o sistema não recusou — cita 3 dos 4 documentos da base (`citation_file_count=3`), reproduzindo ao vivo o sintoma relatado pelo usuário.

## 10. Golden set adversarial

- [x] 10.1 `golden_set.yaml` de `version: 1` para `version: 2`, com comentário explicando o motivo do bump.
- [x] 10.2 Adicionadas 7 perguntas adversariais: `oos-dieta-restritiva` (a falha observada ao vivo), `oos-fis-carpa`, `oos-rpl-streptococcus`, `oos-roi-2030`, `oos-kv-tambaqui`, `oos-densidade-estocagem`, `oos-temperatura-otima` — total de 11 perguntas out_of_corpus, 35 perguntas no conjunto.
- [x] 10.3 `python -m evaluation.validate_golden_set` → OK, 35 perguntas, 40 trechos checados, todos presentes na base.
- [x] 10.4 Confirmado via `git diff`: 83 inserções, 1 deleção (`version: 1` → `version: 2`) — nenhuma entrada original alterada ou removida.

## 11. Baseline de referência

- [x] 11.1 Rodado `python -m evaluation.run_eval --full --k 40 --label pre-fase-a` com o harness corrigido, 35 perguntas (28 originais + 7 adversariais).
- [x] 11.2 Confirmado: `config` inclui `retrieval_k=40` e `use_llm_expansion=true`.
- [x] 11.3 **Baseline salvo em `backend/evaluation/runs/20260802T021236Z-pre-fase-a.json`.** Números, todos medidos com o harness corrigido (não comparáveis diretamente aos runs anteriores a esta change, que tinham golden set v1 e groundedness contra contexto errado):

  | métrica | valor |
  |---|---|
  | mean_recall | 0.812 |
  | mean_selected_chunks | 19.9 |
  | starvation_rate | 0.455 |
  | p95_context_chars | 59624 |
  | refusal_correct_rate | 0.743 |
  | **out_of_corpus_refusal_rate** | **0.182** (2/11 — só as 4 perguntas fáceis originais mais 0 das 7 adversariais mais difíceis foram recusadas corretamente na maioria dos casos) |
  | mean_groundedness | 98.3 |
  | mean_answers_question | 75.6 |
  | mean_mention_coverage | 0.792 |
  | **skeleton_rate** | **0.212** |
  | citation_file_count_mean | 2.27 |
  | citation_precision | 0.753 |
  | custo | $0.0955, 178 chamadas LLM, 7.18s/pergunta |

  O número mais importante deste baseline é `out_of_corpus_refusal_rate=0.182` — dramaticamente mais baixo que os ~0.75 reportados pelos runs anteriores a esta change, porque aqueles mediam contra 4 perguntas fora do escopo fáceis demais. Este é o número real que as changes seguintes do programa (`restore-rag-answer-quality`, `add-rag-self-correction-loop`, `add-hybrid-lexical-vector-search`) precisam melhorar, e é a validação quantitativa de que a Fase 0 (consertar a medição antes de otimizar) era necessária: sem ela, o programa inteiro estaria otimizando contra um alvo fácil demais.
