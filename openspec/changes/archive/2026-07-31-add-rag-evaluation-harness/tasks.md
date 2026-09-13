## 1. Estrutura e leitura do acervo

- [x] 1.1 Criar `backend/evaluation/` com `__init__.py` (o projeto tem histórico de pacotes sem `__init__.py` — ver `app/utils/`).
- [x] 1.2 Extrair o conteúdo real dos 4 documentos indexados (via `SELECT content, metadata FROM documents ORDER BY metadata->>'original_file_name', (metadata->>'page')::int`) para servir de matéria-prima das perguntas. Não inventar perguntas sem olhar o conteúdo.

## 2. Golden set

- [x] 2.1 Definir o schema do `golden_set.yaml`: `id`, `question`, `history` (opcional, lista de turnos anteriores), `scope` (`in_corpus` | `out_of_corpus`), `expected_source_file`, `expected_passages` (trechos literais que a recuperação deve trazer), `must_mention` (pontos que a resposta precisa conter).
- [x] 2.2 Escreveu 15 perguntas `in_corpus` cobrindo **os 3 documentos íntegros** (o BIP 2024 ficou de fora por falha de extração — ver design.md), com mistura deliberada de tipos: quantitativas (valores/tabelas), conceituais, comparativas e metodológicas — os quatro tipos que `_detect_question_type` distingue.
- [x] 2.3 Escrever 3-5 perguntas `out_of_corpus` sobre aquicultura mas ausentes do acervo (não perguntas absurdas — precisam ser plausíveis para o sistema).
- [x] 2.4 Escrever 3-5 sequências de follow-up com `history` preenchido, onde a última pergunta é incompleta sem o contexto anterior.
- [x] 2.5 Revisar o conjunto contra o conteúdo real dos PDFs, confirmando que cada `expected_passage` existe de fato na base.

## 3. Executor — métricas de recuperação (parte barata)

- [x] 3.1 Criar `backend/evaluation/run_eval.py` com modo `--retrieval-only`.
- [x] 3.2 Implementar recuperação por pergunta reaproveitando a lógica de `test_phase4_1_retrieval_manual.py`; como `get_answer` devolve só `str`, chamar a camada de recuperação diretamente (decisão 5 do design).
- [x] 3.3 Métrica: para cada `expected_passage`, verificar se aparece nos chunks recuperados (casamento por sobreposição normalizada, não igualdade exata — os chunks têm fronteiras arbitrárias).
- [x] 3.4 Métricas: recall@k dos trechos esperados, similaridade do melhor chunk, posição do primeiro acerto (rank).
- [x] 3.5 Reportar misses explicitamente por pergunta (requisito "Missed passage is visible").

## 4. Executor — métricas de geração

- [x] 4.1 Modo completo: gerar resposta via `rag_service.get_answer(question, history)`.
- [x] 4.2 Groundedness por LLM-as-judge: passo separado da geração, temperatura 0, avaliando se cada afirmação da resposta se sustenta no contexto recuperado.
- [x] 4.3 Recusa correta: para entradas `out_of_corpus`, detectar se houve recusa; resposta substantiva conta como falha.
- [x] 4.4 Cobertura dos `must_mention` na resposta.
- [x] 4.5 Medir latência por pergunta e acumular custo de API (embeddings + geração + juiz), com preços por modelo em constante única e visível.

## 5. Persistência e comparação

- [x] 5.1 Salvar cada execução em `backend/evaluation/runs/<timestamp>.json` com resultados por pergunta e agregados.
- [x] 5.2 Carimbar na execução a configuração vigente: modelo de embedding (ler o efetivo, não o presumido — hoje é o default silencioso do LangChain), `chunk_size`, `chunk_overlap`, `similarity_threshold`, `k`.
- [x] 5.3 Modo `--compare <run_a> <run_b>`: mostrar deltas das métricas **e** as diferenças de configuração entre as duas execuções.
- [x] 5.4 Saída legível no terminal (tabela por pergunta + resumo agregado), além do JSON.

## 6. Linha de base

- [x] 6.1 Baselines salvos em `backend/evaluation/runs/`: `*-baseline.json` (k=20), `*-baseline-k5.json` (k=5, mais discriminativo) e `*-baseline-full-v2.json` (modo completo, com custo). Configuração confirmada pelo carimbo: ada-002, chunk 4000/500, threshold 0.5.
- [x] 6.2 Registrar no `design.md` desta mudança os números obtidos, para servir de referência às mudanças seguintes.
- [x] 6.3 **Confirmado**: baseline reproduz os problemas conhecidos — `out_of_corpus_refusal_rate` = **0.000** (nenhuma das 4 perguntas fora do escopo foi recusada) e o follow-up `fu-gen-menor-valor` falhou com a menor similaridade do conjunto (0.738). Detalhes no design.md. Requisito original — em especial: recusa correta próxima de 0% nas perguntas `out_of_corpus` (hoje o fallback top-1 sempre entrega algo) e falha nos follow-ups. **Se o baseline NÃO reproduzir isso, o harness está medindo errado** e precisa ser corrigido antes de servir de referência.

## 7. Verificação

- [x] 7.1 Rodar `--retrieval-only` duas vezes seguidas sem mudar nada e confirmar que as métricas de recuperação são idênticas (determinismo).
- [x] 7.2 Introduzir temporariamente uma degradação óbvia (ex.: `k=1`) e confirmar que o recall cai — prova que o harness detecta piora.
- [x] 7.3 Confirmar que `--compare` aponta a diferença de configuração no teste acima.
- [x] 7.4 Custo do baseline completo: US$ 0,068 em 71 chamadas para 23 perguntas (~3 chamadas/pergunta, coerente com o laço de retry). **Ressalva registrada no design**: o callback do LangChain usa tabela de preços própria e reporta ~25% abaixo do cálculo manual com os preços públicos atuais; a ordem de grandeza é confiável, o valor absoluto não. Custo de embeddings fica fora dessa conta e é estimado à parte.
- [x] 7.5 Confirmar que nada em `backend/app/` foi alterado por esta mudança (o RAG de produção segue intacto).
