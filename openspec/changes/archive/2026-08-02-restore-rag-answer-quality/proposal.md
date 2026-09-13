## Why

O usuário reportou piora perceptível na qualidade das respostas do RAG. A investigação (ver `openspec/changes/fix-rag-eval-harness-fidelity` para o instrumento de medição corrigido) identificou dois defeitos concretos na pipeline de produção, ambos em `backend/app/services/rag_service.py`:

**1. Regime binário de seleção de contexto.** `_retrieve_docs_via_rpc` decide o contexto de cada pergunta assim: se algum chunk atinge similaridade ≥ 0.65, usa *só* esses (frequentemente 1-3 chunks); senão, se o melhor candidato atinge ≥ 0.53, usa *todos* os 40 candidatos sem nenhum piso por documento; senão, recusa. Medido nas 28 perguntas do golden set, a contagem de chunks selecionados nunca cai entre 7 e 39 — é sempre fome (1-6) ou inundação (40). Das 6 falhas reais medidas, 5 são fome de contexto (1, 1, 2, 2, 3 chunks). O limiar de 0.65 está acima da similaridade média das perguntas respondíveis (0.628 medido), então o portão de confiança alta quase nunca abre.

**2. Prompt de resposta engessado, que impede a recusa honesta.** Os quatro tipos de pergunta (`conceptual`, `comparative`, `methodological`, `quantitative`) impõem estruturas de seção obrigatórias (`**Dados do Estudo:**`, `COMPARISON:`, `EXPERIMENTAL DESIGN:`, `DATA:`, etc.), incluindo instrução explícita para preencher com "Dados numéricos não disponíveis no contexto" ou a string literal `Empty section.` quando não há dados. **O prompt proíbe a recusa** — uma pergunta fora do escopo não pode virar "não sei", só um formulário vazio. Combinado com o regime de seleção acima (que despeja 40 chunks na zona fraca), o resultado observado ao vivo foi: pergunta sobre "dieta restritiva" (tema ausente da base) → resposta em formulário vazio citando os 4 documentos da base inteira com quase todo o intervalo de páginas.

O usuário também solicitou explicitamente que a estrutura de resposta deixe de ser segmentada em seções obrigatórias e passe a ser prosa fluida, com tópicos apenas quando servem para destacar algo — como a maioria das plataformas de LLM.

Um terceiro problema, secundário mas de custo real: `_add_data_companion_chunks` injeta até 5 chunks por arquivo de origem (não no total) selecionados por densidade de dígitos, sem relação com a pergunta — em uma base de 4 arquivos, até 20 chunks extras por pergunta, cada um exigindo uma varredura completa da tabela do arquivo.

## What Changes

- **BREAKING**: o formato de resposta deixa de impor cabeçalhos de seção obrigatórios por tipo de pergunta. Um único prompt base em prosa contínua substitui os quatro templates; `question_type` passa a ser uma ênfase leve (uma linha), não um template inteiro.
- A resposta usa um sentinela textual explícito (`SEM_RESPOSTA_NO_CONTEXTO`) quando o contexto não permite responder; `generate` detecta o sentinela e devolve a mensagem de recusa real, sem citações.
- O regime binário de seleção de contexto é substituído por uma seleção por ranking com piso mínimo e teto máximo de chunks e orçamento de caracteres — elimina tanto a fome quanto a inundação.
- Um sinal de confiança (`strong`/`partial`) substitui o portão de threshold; respostas em zona de confiança parcial incluem ressalva explícita em prosa, em vez de serem tratadas como certeza ou recusadas.
- Citações passam a refletir só os chunks realmente usados na resposta, com páginas discretas em vez de um intervalo min/max sobre tudo que foi recuperado.
- **BREAKING**: o contrato de `sources` no retorno de `get_answer`/no endpoint `/consultoria/chat` muda de intervalo de página (`page_start`/`page_end`) para lista discreta de páginas.
- A chamada de geração final passa a usar um modelo mais capaz que as chamadas utilitárias (expansão de query, condensação de follow-up), configurável por variável de ambiente.
- Os "data companions" passam a ter um teto total (não por arquivo), critério de elegibilidade mais restrito, e contam contra o orçamento de contexto.
- A checagem de qualidade (`evaluate`) é reescrita para não depender de cabeçalhos de seção, já que eles deixam de existir — dependência obrigatória da mudança de formato, não item independente. O número máximo de retries por resposta cai de 2 para 1, e a avaliação passa a considerar o tipo de pergunta efetivamente usado na geração, não o tipo original quando os dois divergem.
- **Fora de escopo deste change** (fica para `add-rag-self-correction-loop`): o nó `retrieve_retry` e seu bypass do piso de recusa em retry não são alterados aqui — são substituídos por um nó de decisão pré-geração na change seguinte.

## Capabilities

### Modified Capabilities
- `rag-chat-vector-search`: a seleção de contexto, o formato de resposta, as citações e o critério de avaliação de qualidade mudam. A capacidade de recusa honesta (adicionada em `retrieval-refusal-quality`) é preservada e refinada com um nível de confiança intermediário.

## Impact

- `backend/app/services/rag_service.py`: `_build_system_prompt`, `generate`, `_retrieve_docs_via_rpc` (seleção), `_build_sources`/`_extract_source_doc_info`, `evaluate`, `should_retry` (MAX_RETRIES), `_add_data_companion_chunks`, `__init__` (modelos LLM). **Não altera** `retrieve_retry` (fica para `add-rag-self-correction-loop`).
- `backend/app/utils/rag_config.py`: novas constantes de seleção de contexto e modelos de LLM.
- `frontend/components/ChatMessage.tsx`, `frontend/hooks/useChat.ts`: contrato de `sources` muda de span para lista de páginas.
- `backend/tests/test_rag_retrieval_refusal.py`: testes que hoje afirmam o regime binário como comportamento correto precisam ser reescritos.
- Sem mudança de banco de dados nem reingestão de documentos.
