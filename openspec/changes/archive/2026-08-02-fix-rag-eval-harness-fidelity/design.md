## Context

O harness vive em `backend/evaluation/` (`run_eval.py`, `metrics.py`, `golden_set.yaml`, resultados salvos em `runs/*.json`). Ele já existe e já produziu 15 runs históricos — este change não recria o harness, conserta defeitos específicos que foram identificados comparando runs lado a lado e inspecionando respostas reais.

Evidência que motiva cada defeito:

- **Follow-up sem histórico**: `evaluate_retrieval` (`run_eval.py:74-99`) chama `service._retrieve_docs_via_rpc(question["question"], ...)` diretamente — nunca passa `question.get("history")`. As 5 perguntas `fu-*` do golden set têm `history` preenchido; 2 delas (`fu-kv-por-que-importa`, `fu-bip-rpl-menor`) reportam `recall=0.0, retrieved_count=0` no run mais recente, mas a resposta de produção real (que passa por `get_answer`, que condensa o histórico) contém os valores corretos com `mention_coverage=1.00`.
- **Métrica de menção quebrada por formatação**: `_significant_tokens` (`metrics.py`) mantém tokens com dígito ou >4 chars. Para `must_mention: "PRO+MOS com o maior RPL (64,10%)"`, os tokens sobreviventes são `["maior", "64,10%"]`; a resposta do modelo escreve `64.10%` (seguindo o formato do PDF em inglês) → 1/2 = 0.50 < corte de 0.60 → ponto perdido, resposta correta.
- **`is_refusal` acoplado a tamanho**: `len < 400 and has_marker` — o template de resposta atual (que este programa está mudando na change seguinte) facilmente ultrapassa 400 chars mesmo sendo substancialmente uma recusa.
- **`groundedness` mede a coisa errada**: `build_judge` re-recupera contexto com `k=20, use_llm_expansion=False` — um contexto que a resposta nunca viu. `gen-fis-extremos` (resposta correta, valores certos) pontuou `groundedness=0` porque o *re-retrieval do juiz*, não o da resposta, não achou a tabela.
- **`capture_config` incompleto**: grava só 6 campos (`embedding_model`, `embedding_dimensions`, `chunk_size`, `chunk_overlap`, `similarity_threshold`, `llm_model`) no dict `config`. `k` e o uso de expansão de query por LLM SÃO persistidos — como campos soltos no topo do run (`run["k"]`, `run["llm_expansion"]`), lidos corretamente por `compare()` — mas fora de `config`, o que o deixa incompleto como "a" fotografia de configuração e frágil a mudanças futuras (qualquer nova constante de `rag_config` adicionada por uma change deste programa exigiria lembrar de replicar o mesmo padrão de campo solto).
- **Golden set não testa recusa de verdade**: as 4 perguntas `out_of_corpus` (estreptococose, custo de ração, reversão sexual, amônia) são lexical e semanticamente distantes do corpus. A pergunta que efetivamente expôs a regressão ao vivo — "dieta restritiva" — não está representada, nem casos onde o termo certo aparece mas a entidade está errada (espécie, patógeno).

## Goals / Non-Goals

**Goals:**
- Toda métrica reportada deve corresponder ao que a produção realmente faz e ao que o usuário realmente vê.
- Tornar visível o que hoje é invisível: tamanho de contexto, taxa de resposta-esqueleto, precisão de citação.
- Fornecer negativos difíceis o suficiente para calibrar um gate de recusa sem repetir o erro de calibrar contra 4 casos fáceis.
- Manter o harness como observador puro — nenhuma mudança aqui altera o comportamento de `/consultoria/chat`.

**Non-Goals:**
- Não implementa as mudanças de pipeline em si (contexto, prompt, hybrid search) — isso é o restante do programa, em changes subsequentes.
- Não define os valores finais de constantes de configuração (ex.: `CONTEXT_MAX_CHUNKS`) — este change só garante que, quando esses valores forem escolhidos na próxima change, a medição usada para escolhê-los seja confiável.
- Não substitui o LLM-judge por um método determinístico — mantém a abordagem de juiz LLM existente, só corrige o que ele vê e adiciona um segundo juiz com escopo diferente.

## Decisions

**1. Expor um seam de recuperação no serviço, não duplicar a condensação no harness.** `_condense_followup_question` já existe em `rag_service.py`. Em vez do harness reimplementar essa lógica (risco real de divergência silenciosa — é exatamente esse tipo de divergência que motivou centralizar `rag_config.py` no passado), `RAGService` ganha um método que aplica condensação + recuperação e devolve `(docs, trace)`. O harness chama esse método. Alternativa rejeitada: duplicar a lógica de condensação dentro de `run_eval.py` — mais rápido de escrever, mas garante que a próxima mudança na condensação (ex.: Fase B deste programa) quebre silenciosamente a fidelidade do harness de novo.

**2. Trace estruturado em vez de só o resultado final.** Hoje o harness só vê `docs` pós-filtro. Um `trace` dict (`candidate_count`, `top_similarity_raw`, `selected_count`, `context_chars`, `selection_reason`) é devolvido junto, para que `top_similarity` deixe de ser contaminado por recusas (hoje grava `0.000`) e para que a próxima change (que muda a seleção de contexto) tenha uma métrica objetiva de "morri de fome" vs "afoguei" desde o primeiro run.

**3. Dois juízes, escopos deliberadamente diferentes.** `groundedness` (existente, corrigido para ver o contexto real) responde "isto é apoiado no que foi recuperado?". `answers_question` (novo) responde "isto é uma resposta de verdade?", vendo *só* pergunta e resposta — sem contexto, de propósito, para que o juiz não possa justificar um esqueleto vazio como "consistente com o contexto pobre". Alternativa rejeitada: um único juiz com prompt mais complexo pedindo os dois julgamentos numa chamada — mais barato, mas historicamente juízes multi-critério em uma chamada tendem a colapsar nuance (viés de "se está bem formatado, está bem").

**4. Negativos adversariais por categoria de dificuldade, não por volume.** Em vez de adicionar dezenas de perguntas out-of-scope genéricas, adicionar um pequeno conjunto (~5-7) cobrindo os padrões de falha reais identificados: troca de entidade mantendo o vocabulário técnico (espécie errada, patógeno errado), extrapolação de valor (pedir um número que não existe para uma entidade que existe), e a falha observada ao vivo. Volume não ajuda a calibrar um gate — diversidade de padrão de dificuldade ajuda.

**5. Normalização de decimal roda antes de qualquer split de token.** Ordem importa: `,`↔`.` primeiro (formato brasileiro de milhar/decimal), depois separação de milhar, para não confundir `17.000` (dezessete mil) com `17,000` tratado como `17.000` decimal incorretamente. Testar explicitamente contra os casos reais do golden set (`64,10%`, `R$ 17.000`, `0,44`).

## Risks / Trade-offs

- **[Risco] Um seam de recuperação exposto no serviço aumenta a superfície pública de `RAGService`.** Mitigação: nomear e documentar como método de suporte a avaliação, não como API de produção; não expor via `main.py`/HTTP.
- **[Risco] Corrigir o harness pode revelar que a regressão é maior (ou menor) do que a investigação inicial estimou**, já que 2 das 6 falhas atuais eram artefato. Aceito — é o objetivo do change: números confiáveis, mesmo que desconfortáveis.
- **[Trade-off] Um segundo juiz LLM dobra o custo de julgamento por run `--full`.** Aceito — o custo total de um run continua na casa de poucos centavos de dólar (runs históricos ficaram entre $0.001 e $0.07); a alternativa (não medir utilidade) é o que permitiu a regressão passar despercebida.
- **[Risco] Perguntas adversariais podem não ter uma resposta "certa" óbvia para julgar recusa** (ex.: `oos-fis-carpa` pode legitimamente confundir tanto o sistema quanto um avaliador humano). Mitigação: aceitar explicitamente no design que 2 dessas perguntas são esperadas como as mais difíceis do conjunto — servem para expor o limite real do sistema, não para serem "resolvidas" ajustando limiares até passarem.

## Migration Plan

Não há dado de produção migrado. Passos de rollout:
1. Implementar o seam em `rag_service.py` e os testes que o cobrem.
2. Atualizar `run_eval.py`/`metrics.py` para usá-lo.
3. Bump `golden_set.yaml` para `version: 2`, adicionando as entradas adversariais (aditivo — nenhuma entrada existente é removida ou alterada, então runs antigos continuam interpretáveis para as 28 perguntas originais).
4. Rodar `python evaluation/run_eval.py --full --label pre-fase-a` como novo baseline de referência para as changes seguintes.

Rollback: reverter o commit; nenhuma migração de schema ou dado envolvida.

## Open Questions

- Nenhuma pendente para este change. As decisões de calibração de gate de recusa usando o conjunto adversarial ficam para o change `add-rag-self-correction-loop`, que consome este harness corrigido.
