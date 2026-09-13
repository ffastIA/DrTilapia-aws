## Why

O RAG do DrTilápIA vem entregando respostas imprecisas — o próprio histórico do git registra isso (`e8a8459`: "Piorou a qualidade da resposta"). Uma revisão completa identificou regressões concretas de embeddings e chunking, mas **hoje não existe nenhuma forma objetiva de saber se uma mudança melhora ou piora a qualidade**: não há conjunto de perguntas de referência, nem métricas, nem linha de base. Qualquer otimização feita sem isso é palpite, e regressões silenciosas como as atuais podem se repetir sem ninguém perceber.

Esta mudança cria a régua antes de mexer no que está sendo medido. Ela é pré-requisito das mudanças seguintes de otimização do RAG.

## What Changes

- Novo conjunto de avaliação versionado (`golden set`) com perguntas reais sobre os documentos da base, incluindo deliberadamente:
  - perguntas respondíveis, com os trechos-fonte que deveriam ser recuperados
  - perguntas **fora do escopo** da base, para medir se o sistema admite não saber
  - sequências de **follow-up** multi-turno, para medir contexto conversacional
- Novo executor de avaliação que roda o golden set contra o RAG e reporta métricas por pergunta e agregadas: recall dos trechos esperados, similaridade obtida, embasamento da resposta no contexto, taxa de recusa correta, latência e custo.
- Capacidade de **salvar e comparar execuções**, para responder objetivamente "esta mudança melhorou o RAG?".
- Registro de uma linha de base com a configuração atual (ainda com as regressões), que servirá de referência para as mudanças seguintes.

Nenhuma alteração no comportamento do RAG em produção — esta mudança só observa e mede.

## Capabilities

### New Capabilities
- `rag-quality-evaluation`: conjunto de avaliação versionado e execução reprodutível de métricas de qualidade do RAG, com comparação entre execuções.

### Modified Capabilities
Nenhuma. O caminho de consulta do RAG não é alterado por esta mudança.

## Impact

- Novos arquivos sob `backend/evaluation/` (conjunto de avaliação, executor, execuções salvas).
- Reaproveita o diagnóstico já existente em `backend/test_phase4_1_retrieval_manual.py` (múltiplas queries equivalentes, cobertura lexical, ranking por similaridade) em vez de criar do zero.
- Consome a API OpenAI ao executar (embeddings + geração), portanto tem custo por execução — o executor deve reportá-lo.
- Depende dos documentos atualmente indexados (4 arquivos, 49 chunks); o golden set precisa ser reescrito ou revalidado se o acervo mudar substancialmente.
