## Why

O usuário reportou que as respostas do RAG pioraram muito. A investigação confirmou uma regressão real na pipeline (changes `restore-embedding-and-chunking-quality` + `retrieval-refusal-quality`, 2026-08-01) — mas o harness de avaliação (`backend/evaluation/`) não a detecta: o run mais recente reporta `mean_groundedness=92.9` e `out_of_corpus_refusal_rate=0.75`, números que leem como saudáveis, enquanto o usuário observa respostas em formulário vazio ("Dados numéricos não disponíveis no contexto") citando os 4 documentos da base inteira para uma pergunta fora do escopo.

O harness tem defeitos concretos que mascaram a regressão: `evaluate_retrieval` testa perguntas de follow-up sem passar o histórico de conversa (2 das 6 falhas medidas são artefato disso, não falha real); a métrica de cobertura de menção falha em 6 perguntas só por vírgula-vs-ponto decimal (`64,10%` vs `64.10%`); `groundedness` mede fidelidade ao contexto recuperado, não se a resposta responde — por isso um esqueleto de seções vazias pontua alto; e `capture_config` (o dict `config` persistido em cada run) não inclui `k` nem se a expansão de query por LLM estava ligada — esses dois valores são gravados soltos no topo do JSON e usados por `compare()`, mas ficam fora da fotografia de configuração em si, o que dificulta tratar `config` como fonte única ao comparar ou ao estender o harness com constantes futuras.

Sem consertar o instrumento de medição primeiro, qualquer mudança na pipeline (changes seguintes deste programa) será validada contra números não confiáveis.

## What Changes

- `evaluate_retrieval` passa a exercitar a condensação de follow-up (via um seam exposto pelo serviço), em vez de testar a pergunta crua sem histórico.
- `capture_config` passa a incluir `retrieval_k` e `use_llm_expansion` no próprio dict `config`, não só como campos soltos no topo do run.
- A normalização de métricas (`metrics.normalize`) passa a tratar `,`↔`.` como separador decimal equivalente e a normalizar superscripts unicode antes de comparar.
- `is_refusal` deixa de usar um corte de tamanho (`len < 400`) acoplado ao formato da resposta; passa a casar contra as mensagens de recusa reais do sistema.
- O harness passa a registrar um "trace" de recuperação por pergunta (contagem de candidatos, similaridade bruta antes de qualquer filtro, contagem de chunks selecionados, tamanho do contexto em caracteres, motivo da seleção) — hoje `top_similarity` é lido *depois* do filtro de threshold, então uma recusa grava `0.000` e distorce a média.
- Novas métricas agregadas: `mean_selected_chunks`, `p95_context_chars`, `starvation_rate` (perguntas com poucos chunks selecionados), `skeleton_rate` (respostas com padrão de esqueleto vazio), `citation_file_count_mean` e `citation_precision` (usa o `expected_source_file` que o golden set já declara).
- Um segundo juiz LLM, `answers_question`, avalia utilidade da resposta vendo *só pergunta e resposta, sem o contexto* — distinto do `groundedness` existente, que mede fidelidade ao contexto e não pega uma resposta vazia mas "apoiada".
- O juiz de `groundedness` passa a avaliar contra o contexto que a resposta realmente recebeu, não um contexto re-recuperado de forma independente.
- O golden set (`golden_set.yaml`) ganha uma versão 2 com perguntas "fora do escopo, mas próximas" (adversariais) — hoje as 4 perguntas out-of-corpus são lexicalmente distantes do corpus e não testam de verdade a capacidade de recusa.

## Capabilities

### Modified Capabilities
- `rag-quality-evaluation`: o harness passa a medir corretamente follow-ups (com histórico), tamanho de contexto, taxa de esqueleto vazio, precisão de citação, e utilidade da resposta separada de fidelidade ao contexto; o golden set ganha negativos adversariais para calibrar recusa de verdade.

## Impact

- `backend/evaluation/run_eval.py`: `evaluate_retrieval`, `capture_config`, `build_judge`, `summarize`.
- `backend/evaluation/metrics.py`: `normalize`, `is_refusal`.
- `backend/evaluation/golden_set.yaml`: `version: 1 → 2`, novas entradas adversariais.
- `backend/app/services/rag_service.py`: expõe um novo método (seam) que aplica condensação de follow-up + recuperação, reutilizável pelo harness sem duplicar lógica.
- Nenhuma mudança em produção (`/consultoria/chat`) — este change só toca o instrumento de medição.
