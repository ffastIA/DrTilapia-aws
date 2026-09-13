# CAMINHO: backend/app/utils/rag_config.py
"""Configuração explícita de embedding e chunking, lida uma vez do ambiente.

Fonte única para os caminhos de ingestão — no passado, dois caminhos
divergiram silenciosamente (um usava chunk_size=4000 hardcoded, o outro não
passava `model=` ao embedding nenhum), e essa divergência é exatamente o
tipo de regressão que motivou centralizar aqui.
"""
import os

# text-embedding-3-large truncado em 1536 dims: cabe no schema vector(1536)
# e no índice HNSW existentes sem migração, e supera ada-002 e 3-small na
# mesma dimensionalidade.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Restaura a ordem de grandeza da versão que funcionava (1000/200), com
# folga para tabelas científicas que ficariam truncadas em 1000.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Quantidade de candidatos pedidos ao RPC de busca vetorial. Precisa escalar
# com o número de chunks por documento — chunk_size menor gera mais chunks,
# e a mesma janela k passa a cobrir uma fração menor de cada documento.
# 40 foi medido empiricamente (harness) como suficiente para igualar o
# recall da configuração anterior (chunk_size=4000/k=20) mesmo com o
# chunking mais granular atual — ver design.md de retrieval-refusal-quality.
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "40"))
RETRIEVAL_K_RETRY = int(os.getenv("RETRIEVAL_K_RETRY", "40"))

# Limiar de confiança "alta" — acima disso, os candidatos são usados sem
# ressalva. Calibrado contra a distribuição real de similaridade do golden
# set (backend/evaluation/), não escolhido a dedo: com text-embedding-3-large,
# perguntas fora do escopo pontuaram 0.512-0.629, e a pergunta respondível
# mais fraca pontuou 0.539 — não há um único valor que separe os dois grupos
# com perfeição (ver design.md, "Calibração medida"), então o valor aqui
# prioriza não recusar perguntas respondíveis à custa de deixar passar
# algumas perguntas fora do escopo na zona intermediária (ver
# REFUSAL_FLOOR_SIMILARITY). Substitui o antigo PRIMARY_RPC_SIMILARITY_THRESHOLD.
PRIMARY_RPC_SIMILARITY_THRESHOLD = float(os.getenv("PRIMARY_RPC_SIMILARITY_THRESHOLD", "0.65"))

# Piso de similaridade abaixo do qual o sistema recusa (contexto vazio) em
# vez de responder com o melhor match disponível. Entre o piso e o limiar
# acima fica a "zona fraca": todos os candidatos são mantidos (não só o
# top-1) para não sacrificar recall, mas nenhum é tratado como confiável.
# 0.53 foi calibrado para ficar abaixo da pergunta respondível mais fraca
# medida (0.539) e ainda assim recusar o caso mais claro de pergunta fora
# do escopo medido (0.512) — ver tasks.md de retrieval-refusal-quality.
REFUSAL_FLOOR_SIMILARITY = float(os.getenv("REFUSAL_FLOOR_SIMILARITY", "0.53"))

# ── Seleção de contexto por ranking (restore-rag-answer-quality) ────────────
# Substitui o regime binário antigo (só acima do threshold, ou todos os 40
# candidatos na "zona fraca") — medido no golden set que esse regime nunca
# selecionava algo entre 7 e 39 chunks: só fome (1-6, causa da maioria das
# falhas reais medidas) ou inundação (40, ~48% do corpus inteiro em chars).

# Preenchimento mínimo garantido mesmo quando a janela relativa (abaixo)
# produzir menos candidatos que isso — elimina a fome. Rank do primeiro
# chunk correto em perguntas com expansão de query chega a 8 (bip-rpl-extremos);
# um mínimo menor voltaria a starvar essas perguntas.
CONTEXT_MIN_CHUNKS = int(os.getenv("CONTEXT_MIN_CHUNKS", "8"))

# Teto de chunks selecionados, mesmo com muitos candidatos fortes. Com
# expansão de query ligada, alguns golds aparecem em rank 11-14
# (fu-kv-medidas, bip-rpl-extremos) — um teto de 12 os perderia; 16 cobre
# com folga sem voltar à inundação de 40.
CONTEXT_MAX_CHUNKS = int(os.getenv("CONTEXT_MAX_CHUNKS", "16"))

# Orçamento de caracteres do contexto final, nunca cortando abaixo de
# CONTEXT_MIN_CHUNKS. ~22000 chars ≈ 5.5k tokens — vs. o pior caso medido
# do regime antigo (~80k chars/20k tokens com companions), um corte de
# ~3.6x no tamanho de entrada por pergunta.
CONTEXT_CHAR_BUDGET = int(os.getenv("CONTEXT_CHAR_BUDGET", "22000"))

# Margem relativa ao melhor score que define a "janela natural" de chunks
# fortemente relacionados ao top-1 — controla a FORMA da seleção, não a
# contagem (isso é papel de MIN/MAX). Spread observado do melhor candidato
# até o rank 40 é 0.15-0.29; 0.08 tipicamente resulta em 5-15 chunks antes
# do preenchimento mínimo/teto entrarem em ação.
CONTEXT_RELATIVE_MARGIN = float(os.getenv("CONTEXT_RELATIVE_MARGIN", "0.08"))

# Piso absoluto de similaridade para entrar na janela relativa, independente
# de quão longe o top-1 estiver. Mínimos observados no rank 40 variam
# 0.343-0.471; 0.45 fica abaixo do top-1 respondível mais fraco medido
# (0.539), então nunca bloqueia o preenchimento mínimo.
CONTEXT_ABSOLUTE_FLOOR = float(os.getenv("CONTEXT_ABSOLUTE_FLOOR", "0.45"))

# Máximo de arquivos distintos citados numa resposta — uma resposta que cita
# mais que isso está quase certamente citando companions/ruído, não fontes
# genuinamente usadas.
CITATION_MAX_FILES = int(os.getenv("CITATION_MAX_FILES", "3"))

# ── Modelos separados: geração final vs. tarefas utilitárias ────────────────
# Uma única instância de LLM atendia geração de resposta, expansão de query
# e condensação de follow-up. Para Q&A científico com números/tabelas, a
# geração é o gargalo de qualidade mais isolável — subir só ela captura a
# maior parte do ganho a um custo incremental menor (1 chamada cara por
# pergunta, vs. 2-3 chamadas utilitárias baratas que não precisam do mesmo
# raciocínio).
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gpt-4o")
UTILITY_MODEL = os.getenv("UTILITY_MODEL", "gpt-4o-mini")

# ── Data companions (restore-rag-answer-quality: limitado, não removido) ────
# `_add_data_companion_chunks` continua sendo hoje a única fonte de tabelas
# específicas (FIS, RPL) que a busca semântica não recupera bem — ver
# design.md. Teto TOTAL (não por arquivo, que no pior caso injetava até 20
# chunks de arquivos irrelevantes) e desligável para comparação com a busca
# híbrida (change futura).
DATA_COMPANION_ENABLED = os.getenv("DATA_COMPANION_ENABLED", "true").lower() == "true"
DATA_COMPANION_MAX_TOTAL = int(os.getenv("DATA_COMPANION_MAX_TOTAL", "3"))

# ── Busca híbrida léxica + vetorial (add-hybrid-lexical-vector-search) ──────
# Default False até o rollout gradual (grupo 7 do change) confirmar ganho no
# harness sem regressão de out_of_corpus_refusal_rate — ligar manualmente
# via env para validar antes de mudar o default.
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "false").lower() == "true"

# Constante do artigo original que introduziu Reciprocal Rank Fusion
# (Cormack et al. 2009). Não calibrada contra dados deste corpus — 124
# linhas não são amostra suficiente para ajustar um hiperparâmetro com
# confiança; usar o valor padrão da literatura é mais defensável que fingir
# uma calibração que os dados não sustentam.
RRF_K = int(os.getenv("RRF_K", "60"))

# Um termo da pergunta só conta como "discriminativo" (sinal de cobertura
# léxica para o gate de recusa) se aparece em até esta fração dos chunks do
# corpus — acima disso é vocabulário genérico do domínio (ex. "tilápia",
# "tratamento") que casa com quase tudo e não ajuda a distinguir uma
# pergunta dentro do escopo de uma fora. Medido: "tilapia" aparece em 64.5%
# dos chunks (80/124), "rpl" em 1.6% (2/124) — 20% separa claramente os dois.
LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ = float(
    os.getenv("LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ", "0.20")
)

# ── Expansão de query multi-variante (add-multi-query-retrieval-expansion) ──
# Default False até o harness confirmar ganho de recall em perguntas
# coloquiais/imprecisas sem regressão de out_of_corpus_refusal_rate — mesmo
# padrão de rollout gradual de HYBRID_SEARCH_ENABLED. Ao contrário da busca
# híbrida, a fusão aqui é por MÁXIMO de cosseno entre variantes (mesmo
# espaço vetorial em todas), não RRF — preserva a calibração existente de
# REFUSAL_FLOOR_SIMILARITY/CONTEXT_*, nada precisa ser recalibrado.
MULTI_QUERY_EXPANSION_ENABLED = os.getenv("MULTI_QUERY_EXPANSION_ENABLED", "false").lower() == "true"

# Número de variantes de query geradas por uma única chamada LLM (original +
# expansão por sinônimos existente + paráfrase em registro técnico). Fixo
# como ponto de partida — env-configurável como RETRIEVAL_K caso o harness
# mostre que outro valor é melhor.
MULTI_QUERY_VARIANT_COUNT = int(os.getenv("MULTI_QUERY_VARIANT_COUNT", "3"))


def effective_config_summary() -> str:
    return (
        f"embedding_model={EMBEDDING_MODEL} "
        f"embedding_dimensions={EMBEDDING_DIMENSIONS} "
        f"chunk_size={CHUNK_SIZE} chunk_overlap={CHUNK_OVERLAP} "
        f"retrieval_k={RETRIEVAL_K} retrieval_k_retry={RETRIEVAL_K_RETRY} "
        f"refusal_floor_similarity={REFUSAL_FLOOR_SIMILARITY} "
        f"context_min_chunks={CONTEXT_MIN_CHUNKS} context_max_chunks={CONTEXT_MAX_CHUNKS} "
        f"context_char_budget={CONTEXT_CHAR_BUDGET} "
        f"generation_model={GENERATION_MODEL} utility_model={UTILITY_MODEL} "
        f"data_companion_enabled={DATA_COMPANION_ENABLED} "
        f"data_companion_max_total={DATA_COMPANION_MAX_TOTAL} "
        f"hybrid_search_enabled={HYBRID_SEARCH_ENABLED} rrf_k={RRF_K} "
        f"lexical_discriminative_max_doc_freq={LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ} "
        f"multi_query_expansion_enabled={MULTI_QUERY_EXPANSION_ENABLED} "
        f"multi_query_variant_count={MULTI_QUERY_VARIANT_COUNT}"
    )
