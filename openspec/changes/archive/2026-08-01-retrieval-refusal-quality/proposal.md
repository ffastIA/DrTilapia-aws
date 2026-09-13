## Why

A avaliação medida pelo harness (`add-rag-evaluation-harness`) já registrou a falha mais grave do sistema: `out_of_corpus_refusal_rate = 0.000`. Nas 4 perguntas fora do escopo da base, o sistema respondeu com confiança em 100% dos casos, nenhuma recusa. A causa está isolada no código: `_retrieve_docs_via_rpc` (`backend/app/services/rag_service.py`), quando nenhum chunk supera o `similarity_threshold`, não recusa — mantém `deduped[:1]`, o pior match disponível, e entrega isso como contexto para geração. O LLM então produz uma resposta fluente sobre um contexto que não tem relação real com a pergunta.

A mudança anterior (`restore-embedding-and-chunking-quality`) trocou o modelo de embedding e reduziu o `chunk_size`, e mediu (não só suspeitou) que isso multiplicou o número de chunks por documento — para o BIP 2024, de 26 para 57 chunks. Com `k=20` fixo, a mesma janela de recuperação passou a cobrir uma fração menor de cada documento, e o recall pareado caiu de 0,895 para 0,842 nas mesmas 19 perguntas testadas. Foi provado experimentalmente (não suposto) que `k=40` recupera o recall por completo — mas ajustar `k` foi deliberadamente deixado fora daquela mudança, para ser resolvido aqui.

Duas outras falhas concretas, também já medidas: perguntas de follow-up (`fu-*`) recuperam mal porque `retrieve()` embute só a pergunta atual, nunca o histórico da conversa — confirmado no código, não é suposição (`rag_service.py`, nó `retrieve`, chama `_retrieve_docs_via_rpc(state["question"], k=20)`, `state["history"]` não é lido). E o nó `evaluate()` usa uma heurística frágil (`len(answer.strip()) > 150`) que não mede se a resposta de fato usa o contexto recuperado, gerando retries (e custo de LLM) por motivos que não têm relação com qualidade real.

O spec já aceito `rag-chat-vector-search` também está desalinhado do código em dois pontos, que esta mudança corrige: declara threshold de similaridade `0.7` (o código usa `0.5` hoje) e declara que a atribuição de fontes "funciona" (o endpoint hoje sempre devolve `sources: []` hardcoded — esse segundo ponto é corrigido pela mudança seguinte, `add-source-citations`, não por esta).

## What Changes

- `k` de recuperação deixa de ser hardcoded (`20` na busca inicial, `30` nos retries) e passa a ser configurável, com um valor calibrado que restaura o recall medido na linha de base.
- Quando nenhum chunk recuperado supera um piso mínimo de similaridade, o sistema **recusa honestamente** em vez de responder com o melhor match disponível, não importa quão fraco. A recusa não passa pelo LLM (nem custo, nem chance de alucinar sobre contexto ruim).
- O histórico da conversa passa a alimentar a recuperação, não só a geração — perguntas de follow-up incompletas ("E qual a margem por unidade?") são recuperadas com uma versão autocontida da pergunta.
- A heurística de avaliação de qualidade (`evaluate`) para de reprovar respostas por tamanho e passa a considerar corretamente respostas de recusa como terminal (não LOW_QUALITY, não dispara retry).
- A lista fixa de termos de reranking (derivada dos temas do golden set atual) é substituída por um sinal extraído da própria pergunta, para não ficar restrita aos assuntos já testados.
- Cobertura de teste automatizado mínima para a lógica nova (recusa, condensação de follow-up, config lida do ambiente) — hoje zero pytest cobre recuperação/geração.

## Capabilities

### Modified Capabilities
- `rag-chat-vector-search`: threshold e comportamento de recusa passam a refletir o que está implementado (corrige a divergência com o spec aceito), e ganha o requisito novo de recusa honesta.

## Impact

- `backend/app/services/rag_service.py`: nós `retrieve`, `generate`, `evaluate`, `retrieve_retry` do grafo; `_retrieve_docs_via_rpc`; `_rerank_docs`/`_get_rerank_terms`.
- `backend/app/utils/rag_config.py`: novas constantes `RETRIEVAL_K`, `RETRIEVAL_K_RETRY`, `REFUSAL_FLOOR_SIMILARITY`.
- `backend/.env`/`.env.example`: novas variáveis.
- `backend/tests/`: novos testes pytest focados na lógica nova.
- Custo/latência de produção: menos chamadas de LLM desperdiçadas (recusa não chama o LLM; menos retries por causa da heurística de qualidade mais precisa).
- Não altera schema de banco nem exige reingestão — opera inteiramente sobre a recuperação/geração em cima da base já reingerida pela mudança anterior.
