## Why

O RAG usa LangGraph, que existe justamente para permitir ciclos de decisão — recuperar, avaliar, corrigir, tentar de novo. Hoje esse ciclo (`retrieve → generate → evaluate → retrieve_retry`) está implementado, mas não faz nada útil:

- `evaluate` (antes deste programa) julgava qualidade por presença de cabeçalhos de seção no texto gerado — não verificava se a resposta estava correta. A change `restore-rag-answer-quality` já removeu essa checagem (era incompatível com o novo formato em prosa) e a substituiu por checagens básicas de não-vazio/relevância, mas não introduziu nenhum julgamento de qualidade real.
- `retrieve_retry` reage a uma reprovação relaxando completamente as proteções (`skip_threshold=True`, que ignora tanto o limiar de confiança quanto o piso de recusa) e usa a pergunta crua em vez da query condensada de follow-up — na prática, "tentar de novo" hoje significa "recuperar com validação desligada", não "recuperar melhor".
- Não existe nenhuma verificação de que os números citados numa resposta realmente vêm do contexto fornecido — num corpus inteiramente numérico (índices, percentuais, valores em reais), esse é o modo de falha mais grave possível e não tem nenhuma rede de segurança.
- A decisão de "o contexto é suficiente?" é feita hoje só por um número (similaridade de cosseno) — que provadamente não separa perguntas dentro/fora do escopo neste corpus: uma pergunta claramente fora do escopo ("estreptococose") marca 0.620 de similaridade, acima de perguntas legítimas que marcam 0.539 e 0.544. Não existe um único limiar numérico que resolva essa sobreposição.

O padrão estabelecido para esse tipo de sistema (Self-RAG / Corrective RAG) é decidir **antes** de gerar se o contexto é suficiente, e verificar **depois** de gerar se a resposta é sustentada pelo que foi fornecido — não inferir qualidade a partir do formato do texto de saída.

## What Changes

- Novo nó `grade_context`, executado depois de `retrieve` e antes de `generate`: julga semanticamente (via LLM barato) se o contexto recuperado é suficiente, parcial ou insuficiente para responder à pergunta — substitui a decisão implícita baseada só em similaridade de cosseno.
- Quando o contexto é insuficiente, o sistema reformula a query de busca e tenta recuperar novamente **uma única vez**; se ainda insuficiente, recusa honestamente. Isso substitui o comportamento atual de `retrieve_retry`.
- **BREAKING** (interno): `retrieve_retry` e seu bypass total das proteções (`skip_threshold=True`) são removidos; a lógica de nova tentativa passa a viver em `grade_context` e nunca ignora o piso de recusa.
- Novo nó `verify_numeric`, executado depois de `generate`: extrai por regex os valores numéricos presentes na resposta e confirma que cada um aparece no contexto fornecido — sem chamada de LLM, custo zero. Números não suportados disparam uma única regeneração com instrução de correção listando os valores ofensores.
- Opcional/condicional: decomposição de perguntas de "maior e menor" (que hoje concentram a maioria das falhas de recall) em sub-buscas — implementado só se a medição mostrar que a janela de contexto da change anterior não resolve sozinha.

## Capabilities

### New Capabilities
- `rag-self-correction`: verificação e correção da resposta dentro do próprio ciclo de geração — julgamento de suficiência de contexto antes de gerar, e verificação de suporte numérico depois de gerar, com no máximo uma tentativa de correção em cada ponto.

## Impact

- `backend/app/services/rag_service.py`: `_build_graph` (nova topologia do grafo), novo nó `grade_context`, novo nó `verify_numeric`, remoção de `retrieve_retry`, `State` (novos campos: `context_sufficiency`, `numeric_verification_attempted` ou equivalente).
- Depende de `restore-rag-answer-quality` (formato de resposta em prosa, seleção de contexto por ranking) e usa o golden set adversarial de `fix-rag-eval-harness-fidelity` para calibrar `grade_context`.
- Sem mudança de banco de dados.
- Custo: +1 chamada de LLM barata por pergunta (`grade_context`); `verify_numeric` é regex, sem custo; retries líquidos por pergunta não aumentam (o teto continua em 1 tentativa de correção por etapa).
