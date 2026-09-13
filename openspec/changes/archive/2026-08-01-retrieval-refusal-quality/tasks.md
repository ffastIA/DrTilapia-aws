## 1. Configuração

- [x] 1.1 `RETRIEVAL_K` (40), `RETRIEVAL_K_RETRY` (40), `PRIMARY_RPC_SIMILARITY_THRESHOLD` (0,65, migrado para `rag_config.py`), `REFUSAL_FLOOR_SIMILARITY` (0,53) em `backend/app/utils/rag_config.py`.
- [x] 1.2 Variáveis em `backend/.env.example` (com comentário explicando a calibração) e `backend/.env`.
- [x] 1.3 Literais `k=20`/`k=30` substituídos pelas novas constantes nos nós `retrieve`/`retrieve_retry`.
- [x] 1.4 Log de inicialização estendido com `retrieval_k`, `retrieval_k_retry`, `refusal_floor_similarity`.

## 2. Recusa honesta

- [x] 2.1 `_retrieve_docs_via_rpc`: quando nada supera o threshold, checa o piso de recusa. Abaixo do piso → lista vazia. **Ajuste feito durante a calibração**: entre o piso e o threshold ("zona fraca"), mantém TODOS os candidatos (não só o top-1) — restringir a 1 sacrificaria recall de perguntas legítimas que caem nessa zona pela sobreposição real de scores (ver design.md).
- [x] 2.2 Nó `retrieve`: lista vazia → `insufficient_context=True`, `context=""`.
- [x] 2.3 Nó `generate`: `insufficient_context` → mensagem de recusa fixa (pt-BR/en) sem chamar `self.llm`; marca `evaluation="REFUSED"`.
- [x] 2.4 Nó `evaluate` faz short-circuit no início quando `evaluation` já é `"REFUSED"` — não reavalia como resposta normal. `should_retry` já tratava qualquer valor != `"LOW_QUALITY"` como terminal, então não precisou de mudança adicional.

## 3. Qualidade da avaliação

- [x] 3.1 Removido o piso arbitrário `len > 150`; mantida checagem de resposta vazia como rede de segurança mínima.
- [x] 3.2 Confirmado: checagens por seção continuam funcionando sem o piso de tamanho como pré-requisito.

## 4. Histórico na recuperação

- [x] 4.1 `_condense_followup_question(question, history, lang)` — mesmo padrão de chamada LLM de `_expand_query_with_llm`, com fallback mecânico (concatenação do turno anterior) se a chamada falhar.
- [x] 4.2 Nó `retrieve` condensa a pergunta antes de buscar quando há histórico.
- [x] 4.3 Confirmado: a pergunta condensada é usada só para a busca; `state["question"]` original permanece intacto (usado no prompt de geração, que já recebe o histórico completo separadamente).

## 5. Reranking generalizado

- [x] 5.1 `_get_rerank_terms` substituído: extrai termos de conteúdo (>4 caracteres, fora de uma lista de stopwords) da própria pergunta, em vez de 3 listas fixas hardcoded.
- [x] 5.2 `_rerank_docs`/`_score_doc_bonus` inalterados na forma (bônus aditivo sobre a similaridade), só a fonte dos termos mudou.
- [x] 5.3 Não há regressão nos temas antes hardcoded — os termos de conteúdo desses temas (tilápia, restrição alimentar, metabolismo) continuam sendo extraídos normalmente quando aparecem na pergunta, só que agora por um mecanismo geral, não uma lista fixa desses três temas específicos.

## 6. Calibração do piso de recusa

- [x] 6.1 Rodado `run_eval.py --retrieval-only --k 40` e inspecionada a distribuição real de `top_similarity`.
- [x] 6.2 **Medido**: `in_corpus` (exceto follow-ups) 0,539–0,816; `out_of_corpus` 0,512–0,629. Overlap real entre 0,539–0,629 — não existe piso único perfeito. Escolhido `threshold=0,65`/`floor=0,53`, priorizando não recusar perguntas respondíveis. Números completos em `design.md`.
- [x] 6.3 Registrado explicitamente em `design.md`: a sobreposição não resolvida (uma pergunta fora do escopo — `oos-qualidade-agua-amonia`, score 0,537 — cai na zona fraca e ainda recebe resposta, embora já visivelmente qualificada/hedged, não confiante).

## 7. Testes

- [x] 7.1 `backend/tests/test_rag_retrieval_refusal.py::TestRefusalFallback` — 4 testes: acima do threshold, zona fraca mantém todos os candidatos, abaixo do piso recusa, retry ignora a lógica de recusa (`skip_threshold=True`).
- [x] 7.2 `TestConfigFromEnvironment` — confirma `RETRIEVAL_K`/`REFUSAL_FLOOR_SIMILARITY` lidos do ambiente, não hardcoded.
- [x] 7.3 `TestFollowupCondensation` — 3 testes: sem histórico não altera a pergunta (e não chama o LLM); com histórico condensa via LLM; falha do LLM cai no fallback mecânico. Total: 8/8 testes passando.

## 8. Verificação

- [x] 8.1 `python -m evaluation.run_eval --full --k 40` (configuração real de produção — expansão de query por LLM ligada).
- [x] 8.2 **Resultado**: `out_of_corpus_refusal_rate` 0,000 → 0,75; `refusal_correct_rate` 0,964. Critério de aceite da recusa cumprido com folga.
- [x] 8.3 **Achado durante a verificação**: o `mean_recall` agregado do `--full` (0,729) subestima a qualidade real — a função de medição de retrieval do harness não passa pelo grafo (não se beneficia da condensação de follow-up) e usa uma expansão de query LLM não-determinística e desacoplada da geração real. Confirmado por amostragem manual: 7 perguntas marcadas com recall baixo/zero pela medição tinham respostas geradas corretas e completas. Registrado como gap do harness (não desta mudança) em `design.md` — não bloqueante, já que a métrica confiável (recusa) está diretamente ligada à resposta real.
- [x] 8.4 `python test_phase6_post_reindex_success_manual.py`: ✅ APROVADO.
- [x] 8.5 Teste manual via `rag_service.get_answer` com pergunta claramente fora do escopo ("receita de bolo de chocolate"): recusa honesta confirmada, zero chamadas ao LLM (só log de `retrieve`, nenhum de geração).
- [x] 8.6 Teste manual de follow-ups reais (via harness `--full`, perguntas `fu-*` do golden set): respostas corretas confirmadas por inspeção manual (`fu-bia-margem` → 56,47%; `fu-bip-rpl-menor` → tabela completa de RPL com MOS=21,02% identificável como menor; `fu-gen-menor-valor` → SAL=3,04 corretamente identificado).
