## Context

Este change assume que `restore-rag-answer-quality` já está aplicado: resposta em prosa (sem cabeçalhos), seleção de contexto por ranking com piso/teto (`CONTEXT_MIN_CHUNKS`/`CONTEXT_MAX_CHUNKS`/`CONTEXT_CHAR_BUDGET`), sinal de confiança `strong`/`partial`, sentinela `SEM_RESPOSTA_NO_CONTEXTO`. Também assume `fix-rag-eval-harness-fidelity` aplicado, cujo golden set adversarial (perguntas fora do escopo mas lexicalmente próximas ao corpus — troca de espécie, troca de patógeno) é o instrumento usado para calibrar este change.

Grafo atual (pós `restore-rag-answer-quality`): `retrieve → generate → evaluate → (retrieve_retry → generate)*`, com `retrieve_retry` chamando `_retrieve_docs_via_rpc(..., skip_threshold=True)` — que ignora tanto `PRIMARY_RPC_SIMILARITY_THRESHOLD` quanto `REFUSAL_FLOOR_SIMILARITY` — e usando `state["question"]` cru em vez de `state["retrieval_query"]` (a versão condensada com histórico).

Evidência que motiva o redesenho:
- Similaridade de cosseno não separa in/out-of-corpus neste corpus (0.620 de uma pergunta claramente fora do escopo vs. 0.539-0.544 de perguntas legítimas) — documentado e ainda válido após a mudança de seleção de contexto, porque a seleção muda *quanto* contexto é usado, não decide *se* a pergunta é respondível.
- `retrieve_retry` hoje é estritamente pior que não tentar de novo em alguns casos: uma pergunta que quase foi recusada (abaixo do piso) pode, no retry, ser "resgatada" com 40 chunks arbitrários porque o piso foi desligado.

## Goals / Non-Goals

**Goals:**
- Decidir se o contexto é suficiente antes de gastar uma chamada de geração nele.
- Nunca produzir um número na resposta final que não esteja no contexto fornecido.
- Ter no máximo uma tentativa de correção em cada ponto de decisão — sem loops abertos nem retries que multiplicam custo sem multiplicar qualidade.
- Nunca contornar o piso de recusa, em nenhuma tentativa.

**Non-Goals:**
- Não substitui a busca vetorial por busca híbrida (change `add-hybrid-lexical-vector-search`) — `grade_context` trabalha com o que a recuperação (vetorial, nesta change) devolve; melhorar a recuperação em si é escopo da change seguinte.
- Não implementa decomposição de perguntas de extremos incondicionalmente — só como item condicional, avaliado depois de medir se `grade_context` + a janela de contexto já resolvem essas perguntas.
- Não muda o formato de resposta (prosa) nem a seleção de contexto — herda de `restore-rag-answer-quality` sem alteração.

## Decisions

**1. `grade_context` como nó separado, antes de `generate`, não como parte de `evaluate` depois.** Julgar suficiência de contexto e julgar qualidade de resposta são perguntas diferentes, respondíveis com informação diferente: a primeira só precisa da pergunta + contexto (não precisa esperar uma resposta ser gerada, gastando uma chamada mais cara). Fazer essa decisão antes economiza a chamada de geração completa quando o contexto já é claramente insuficiente, e é o que permite reformular a query e tentar de novo *antes* de qualquer resposta ruim existir — hoje o sistema só descobre que o contexto era ruim depois de já ter gerado (e cobrado) uma resposta a partir dele.

   *Alternativa considerada*: manter a decisão só no `evaluate` pós-geração, como hoje. Rejeitada porque não resolve o problema de fundo — decidir depois de gerar significa que já se pagou o custo da geração ruim, e a única ação disponível é descartar e tentar de novo do zero, sem ganho de informação sobre *por que* a primeira tentativa falhou.

**2. Três estados (`sufficient`/`partial`/`insufficient`), não dois.** Um julgamento binário reproduziria o mesmo problema do threshold de similaridade — força uma linha reta sobre uma distribuição que se sobrepõe de verdade. `partial` mapeia diretamente para o sinal de confiança já existente (`context_confidence` de `restore-rag-answer-quality`) e não exige nova tentativa; só `insufficient` dispara reformulação.

**3. Reformulação de query com no máximo 1 tentativa adicional, nunca desligando o piso de recusa.** Ao contrário do `retrieve_retry` atual, a nova tentativa usa uma query reformulada (reaproveitando `_expand_query_for_retry`, que já existe) mas passa pelos mesmos `_select_context_docs`/piso de recusa da recuperação original — nenhum parâmetro de bypass. Se a segunda tentativa também for `insufficient`, o sistema recusa. Isso é estritamente mais seguro que hoje, onde o retry pode "resgatar" com contexto ruim uma pergunta que o piso original teria recusado.

   *Alternativa considerada*: múltiplas tentativas com reformulações progressivamente mais amplas. Rejeitada — dados do programa mostram que a segunda tentativa nunca foi observada melhorando o resultado; mais tentativas só aumentam custo e latência sem sinal de que ajudam.

**4. `verify_numeric` é regex, não LLM.** Extrair números de um texto e conferir presença no contexto (com a normalização decimal já implementada em `fix-rag-eval-harness-fidelity`) é um problema determinístico — não precisa de julgamento. Rodá-lo como checagem de custo zero depois de cada geração é estritamente melhor que confiar só na instrução de "não invente números" do prompt, que já existe e claramente não é suficiente sozinha (é exatamente o tipo de instrução que modelos ocasionalmente ignoram sob pressão de completar uma resposta).

   *Alternativa considerada*: um segundo juiz LLM para verificar fidelidade numérica. Rejeitada — mais caro, mais lento, e menos confiável que comparação de string para uma tarefa puramente sintática (o número está ou não está no texto do contexto).

**5. Regeneração pós-`verify_numeric` recebe a lista de números não suportados, não só "tente de novo".** Uma instrução de correção específica ("os seguintes valores não aparecem no contexto fornecido: X, Y — remova-os ou corrija-os") dá ao modelo informação acionável, em vez de repetir a mesma chamada esperando um resultado diferente.

**6. Decomposição de perguntas de extremos fica condicional, não implementada de imediato.** As perguntas afetadas (`gen-fis-extremos`, `bip-rpl-extremos`, `fu-gen-menor-valor`, `fu-bip-rpl-menor`) já se beneficiam de duas mudanças anteriores no programa (janela de contexto maior, companions restritos mas presentes). Implementar decomposição antes de medir esse efeito arrisca resolver um problema que já não existe, adicionando complexidade permanente (uma sub-chamada de LLM + fusão de resultados) para um ganho não confirmado.

## Risks / Trade-offs

- **[Trade-off] +1 chamada de LLM por pergunta (`grade_context`), mesmo no caminho feliz.** Aceito — é um modelo utilitário barato (`UTILITY_MODEL`, já `gpt-4o-mini` desde a change anterior), e o custo evitado (gerar uma resposta completa a partir de contexto insuficiente, potencialmente seguida de regeneração por número não suportado) tende a compensar.
- **[Risco] `grade_context` pode divergir do piso de recusa por similaridade** — uma pergunta pode ter similaridade acima do piso mas ser julgada `insufficient` semanticamente, ou vice-versa. Aceito como comportamento pretendido: a similaridade de cosseno já provou não separar bem os casos; quando os dois sinais divergem, o julgamento semântico tem precedência sobre o numérico para a decisão de gerar, mas o piso de recusa numérico continua como rede de segurança de custo zero antes mesmo de chamar `grade_context`.
- **[Risco] `verify_numeric` pode ter falsos positivos** (número genuinamente derivado por cálculo simples a partir de dois valores do contexto, ex. uma diferença percentual, não aparece literalmente). Mitigação: a normalização decimal já cobre formatos equivalentes; falsos positivos residuais resultam em uma regeneração extra (custo, não erro) — o `evaluate` final ainda aceita a resposta regenerada mesmo que a segunda verificação também sinalize, para não recusar indefinidamente uma resposta correta com aritmética derivada.
- **[Risco] Remover `retrieve_retry` é uma mudança de comportamento observável em perguntas hoje "resgatadas" pelo bypass do piso.** Aceito e esperado — essas eram, por definição, respostas construídas a partir de contexto que o próprio sistema havia sinalizado como abaixo do piso de confiança; o comportamento correto é recusar ou reformular, não responder mesmo assim.

## Migration Plan

Sem migração de dados.
1. Implementar `verify_numeric` primeiro (determinístico, sem dependência de calibração) e integrá-lo ao fluxo pós-`generate` existente.
2. Implementar `grade_context`, inicialmente em modo de observação (log, sem alterar o fluxo) para coletar julgamentos contra o golden set adversarial sem afetar produção.
3. Calibrar o comportamento de `sufficient`/`partial`/`insufficient` contra o golden set adversarial (`fix-rag-eval-harness-fidelity`), incluindo os casos deliberadamente difíceis (`oos-fis-carpa`, `oos-rpl-streptococcus`) — aceitar que esses podem continuar sendo os mais difíceis do conjunto, não ajustar até "passarem" artificialmente.
4. Substituir `retrieve_retry` pelo novo fluxo condicional a `grade_context`.
5. Rodar `run_eval.py --full` e comparar contra o baseline da change anterior (`pos-fase-a`).

Rollback: reverter o commit restaura `retrieve_retry`; não há estado persistido.

## Open Questions

- ~~Se a decomposição de perguntas de extremos (item condicional) for necessária, ela é uma sub-etapa deste change ou merece change própria~~ — **resolvida (grupo 6): não é necessária.** Medido contra `pos-self-correction-v2`: 3 das 4 perguntas de extremos originalmente sinalizadas (`gen-fis-extremos`, `bip-rpl-extremos`, `fu-bip-rpl-menor`) já passam com recall=1.00 graças a `grade_context` + à janela de contexto de `restore-rag-answer-quality`. A única que ainda mostra `recall=0.0` na métrica (`fu-gen-menor-valor`, mais o par relacionado `gen-area-file`) tem resposta final **correta e bem fundamentada** (`groundedness=100`, valores exatos 7,05/3,04 batendo com `must_mention`) — a reformulação de `reformulate_and_retrieve` encontra o chunk certo numa 2ª tentativa que a métrica `recall` (medida só na 1ª tentativa, sem reformulação) não enxerga. Não há problema de "duas buscas disfarçadas de uma" para decompor; há uma lacuna de medição no harness (`recall` não reflete o resultado pós-reformulação), documentada como item futuro fora de escopo em `tasks.md` (grupo 6).
