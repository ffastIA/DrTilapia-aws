## Context

Corpus: `public.documents`, 124 linhas, coluna `content` (texto do chunk), coluna `embedding` (vector(1536)), `metadata` JSONB. Função existente:

```sql
CREATE OR REPLACE FUNCTION public.rpc_vector_search(query_vector jsonb, limit_count integer DEFAULT 5)
 RETURNS TABLE(id text, content text, metadata jsonb, similarity double precision)
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
...
    ORDER BY d.embedding <=> query_embedding ASC
    LIMIT limit_count;
END;
$function$
```

Corpus é bilíngue: 2 documentos em português (`BIA_RAG.pdf`, `Indice volumetrico abate.pdf`), 2 em inglês (`BIP 2024 publicado.pdf`, `Genetic and phenotypic characterization...pdf`).

Casos de falha que motivam este change (medidos contra o golden set, pipeline já com as duas changes anteriores aplicadas): perguntas cuja resposta correta depende de casar um termo específico — sigla (`RPL`, `FIS`, `KV`, `MOS`), valor numérico exato (`64.10`, `1.26 x 10⁸`), ou nome de tratamento (`PRO+MOS`) — que a busca vetorial rankeia abaixo do necessário porque o embedding representa o *tópico* do trecho, não a presença literal do termo.

## Goals / Non-Goals

**Goals:**
- Perguntas de busca por termo exato passam a recuperar o chunk correto de forma confiável.
- A migração de schema não exige reprocessar nenhum documento existente.
- `rpc_vector_search` continua funcionando exatamente como hoje, para que a busca híbrida possa ser desligada sem regressão.
- Um segundo sinal, independente da similaridade de cosseno, melhora a confiabilidade do gate de recusa.

**Non-Goals:**
- Não implementa correção de acentuação (`índice` vs `indice`) de forma completa — `unaccent` fica como melhoria futura; mitigação parcial do lado Python é suficiente para este change.
- Não funde as duas buscas numa única função RPC — mantém duas funções e fusão em Python, deliberadamente (ver Decisão 2).
- Não reindexa nem re-embeda documentos.
- Não altera a seleção de contexto por ranking (`_select_context_docs`) além de trocar a fonte do score de ordenação — piso/teto/orçamento de `restore-rag-answer-quality` permanecem.

## Decisions

**1. Coluna gerada com `to_tsvector` de 2 argumentos, três configurações concatenadas.**
```sql
ALTER TABLE public.documents
  ADD COLUMN content_tsv tsvector
  GENERATED ALWAYS AS (
      to_tsvector('simple',     coalesce(content, '')) ||
      to_tsvector('portuguese', coalesce(content, '')) ||
      to_tsvector('english',    coalesce(content, ''))
  ) STORED;

CREATE INDEX CONCURRENTLY documents_content_tsv_gin
  ON public.documents USING gin (content_tsv);
```
A forma de **dois argumentos** `to_tsvector(regconfig, text)` é `IMMUTABLE` e por isso legal numa coluna gerada; a forma de um argumento é só `STABLE` (depende de `default_text_search_config`) e é rejeitada pelo Postgres nesse contexto — armadilha comum o suficiente para documentar aqui. `simple` preserva `fis`, `rpl`, `mos`, `64.10` sem stemming (o que buscas por sigla/valor exigem); `portuguese`/`english` cobrem os dois idiomas do corpus com stemming normal para recall de linguagem natural. `CREATE INDEX CONCURRENTLY` não roda dentro de transação — passo de migração separado do `ALTER TABLE`.

*Alternativa rejeitada*: coluna calculada em trigger em vez de `GENERATED ... STORED`. Mais complexidade operacional (trigger para manter, risco de dessincronia) sem benefício — `GENERATED STORED` já resolve a atualização automática de forma nativa e mais simples.

**2. Duas funções RPC com fusão em Python, não uma função fundida no banco.** A busca vetorial é a única parte da pipeline que hoje funciona sem ressalvas — colocar em risco `rpc_vector_search` fundindo-a com lógica nova é desnecessário: a tabela tem 124 linhas, então uma segunda chamada RPC custa milissegundos, não é um problema de performance real. Fusão em Python é testável isoladamente (mockando as duas chamadas RPC) e o rollback é uma flag booleana, não uma reversão de DDL.

**3. RRF (Reciprocal Rank Fusion), não combinação de score bruto.** Similaridade de cosseno e `ts_rank_cd` vivem em escalas completamente diferentes e não comparáveis diretamente. RRF (`score += 1/(k + rank)`) usa só a posição de cada documento em cada lista, não o valor do score — é a técnica padrão para esse problema exatamente porque não exige normalizar escalas incompatíveis. `RRF_K=60` é a constante do artigo original que introduziu a técnica; não é ajustada por dados porque 124 linhas não são amostra suficiente para calibrar um hyperparâmetro com confiança — usar o valor padrão da literatura é mais defensável que fingir uma calibração que os dados não sustentam.

**4. `to_tsquery` sobre termos unidos por `OR` (`|`), construídos em Python — não `websearch_to_tsquery`/`plainto_tsquery`.** Essas funções nativas do Postgres unem termos com `AND` por padrão; uma pergunta como "protocolo de tratamento recomendado para estreptococose" viraria uma busca com todos os termos obrigatórios simultaneamente, que não bate com nada. Construir os termos em Python (reaproveitando `_RERANK_STOPWORDS`, já existente) e uni-los com `|` permite ranking por quantos termos casam, sem exigir que todos casem.

**5. Gate de recusa ganha um segundo sinal — cobertura léxica discriminativa — mas o piso de similaridade de cosseno continua sendo a primeira barreira.** Regra proposta: recusa se `similaridade_topo < REFUSAL_FLOOR_SIMILARITY` (como hoje) **ou** (`similaridade_topo` na zona intermediária **e** nenhum termo discriminativo da pergunta casa lexicalmente no corpus). "Discriminativo" exclui termos genéricos do domínio (ex. "tilápia", "tratamento") que casam com quase todo chunk e não ajudam a distinguir uma pergunta dentro do escopo de uma fora — medido por frequência de documento: um termo só conta se aparece em ≤ 20% dos chunks. Isso exige devolver frequência de documento por termo da própria função RPC ou de uma função companheira leve.

   *Risco explícito*: perguntas que trocam só a entidade mantendo vocabulário técnico específico do domínio (ex. pedir o mesmo índice `FIS` de uma espécie que não está na base) vão pontuar alto nos dois sinais — cosseno alto (o vocabulário é idêntico) e cobertura léxica alta (os termos técnicos aparecem de verdade no corpus, só a entidade está errada). Este é exatamente o tipo de caso que o `grade_context` de `add-rag-self-correction-loop` (julgamento semântico) resolve e um sinal léxico não resolve sozinho — as duas camadas são complementares, não substitutas.

**6. Remover o bônus de reranking manual (`_score_doc_bonus`) em vez de mantê-lo ao lado da fusão.** O bônus hoje soma até +0.2/+0.3 (proporcional ao número de termos casados por substring, sem limite) contra uma banda de decisão de 0.12 entre o piso de recusa e o limiar de confiança — grande o suficiente para inverter decisões, e casa por substring sem respeitar fronteira de palavra (`mos` casa dentro de `mostrar`). A fusão RRF é a versão correta e limitada do mesmo princípio (dar peso a casamento léxico); manter os dois seria redundante e reintroduziria a mesma distorção que a fusão corrige.

**7. Aposentar os companions só depois de confirmar paridade, não como parte automática desta change.** `_add_data_companion_chunks` (já limitado em `restore-rag-answer-quality`) continua até uma medição explícita confirmar que a busca híbrida recupera as mesmas tabelas (`gen-fis-extremos`, `bip-rpl-extremos`) sem ele — evita repetir o padrão de remover um mecanismo funcional antes de confirmar que o substituto cobre o mesmo caso.

## Risks / Trade-offs

- **[Risco] `ALTER TABLE ... ADD COLUMN ... GENERATED ... STORED` reescreve a tabela inteira sob `ACCESS EXCLUSIVE` lock.** Mitigação: em 124 linhas isso é da ordem de milissegundos — risco teórico, não prático neste corpus; documentado para o caso de o corpus crescer substancialmente antes desta migração ser aplicada.
- **[Trade-off] Acentuação não é tratada** (`índice` vs `indice` não casam via full-text sem `unaccent`). Aceito como limitação conhecida; mitigação parcial do lado Python (normalização NFKD já existe em `_is_answer_relevant`, reaproveitável na construção da query léxica) cobre parte do ganho a custo zero.
- **[Risco] Fundir vetorial e léxico muda o significado de "score"** — o piso de recusa foi calibrado contra cosseno puro; aplicá-lo ao score RRF fundido seria incorreto. Mitigação: o piso de recusa continua lido do score de cosseno bruto, nunca do score fundido — a fusão só decide *ranking e top-N*, nunca a decisão binária de recusa por similaridade.
- **[Risco] Dois RPCs por pergunta em vez de um** aumenta ligeiramente a latência de rede. Aceito — marginal frente ao tempo de geração do LLM, e a flag `HYBRID_SEARCH_ENABLED` permite desligar sem deploy se a latência se mostrar um problema real em produção.
- **[Risco de segurança]** Uma função RPC nova precisa repetir o padrão de segurança já corrigido nas funções existentes (achado M2 do `docs/auditoria-fullstack.md`): `SET search_path = public` explícito e `REVOKE ... FROM anon, authenticated` / `GRANT ... TO service_role`. Tratado como requisito da migração, não como opcional.

## Migration Plan

1. Aplicar a migração de schema (`ALTER TABLE` + `CREATE INDEX CONCURRENTLY`) — aditiva, sem tocar dado existente, sem downtime esperado dado o tamanho da tabela.
2. Criar `rpc_lexical_search` com as permissões restritivas corretas desde a criação.
3. Implementar a fusão em Python atrás de `HYBRID_SEARCH_ENABLED=False` por padrão; validar contra o golden set com a flag ligada manualmente antes de mudar o default.
4. Ligar `HYBRID_SEARCH_ENABLED=True` por padrão só depois de confirmar ganho no harness sem regressão de `out_of_corpus_refusal_rate`.
5. Remover `_score_doc_bonus`/`_rerank_docs`.
6. Confirmar paridade nas perguntas dependentes de companions; só então desligar `DATA_COMPANION_ENABLED`.

Rollback: `HYBRID_SEARCH_ENABLED=False` restaura o comportamento de busca vetorial pura instantaneamente, sem reverter a migração de schema (que é inofensiva mesmo não utilizada). Reverter o schema em si (`DROP COLUMN`/`DROP INDEX`) só seria necessário em caso de problema na própria migração, não como parte do rollback funcional normal.

## Open Questions

- Se a latência de duas chamadas RPC sequenciais se mostrar perceptível em produção (não esperado neste volume de dados), considerar paralelizar as duas chamadas ou migrar para uma função RPC fundida no banco — adiado até haver evidência de que é necessário.
