# CAMINHO: backend/tests/test_hybrid_search.py
"""Testes de `add-hybrid-lexical-vector-search`: construção de query léxica,
fusão RRF, e preservação do piso de recusa em cosseno puro mesmo com a
fusão ativa.

Cobertura deliberada do risco central do design: fundir vetorial e léxico
muda o significado de "score" — o piso de recusa foi calibrado contra
cosseno puro, então precisa continuar lendo o cosseno bruto, nunca o score
RRF fundido (ver design.md, decisão 5 e riscos).
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service
from app.utils.rag_config import CONTEXT_ABSOLUTE_FLOOR, REFUSAL_FLOOR_SIMILARITY


@pytest.fixture
def service():
    return get_rag_service()


def _vector_doc(similarity: float, chars: int = 100, db_id: str = "id") -> Document:
    return Document(
        page_content="x" * chars,
        metadata={"similarity": similarity, "db_id": db_id},
    )


def _lexical_doc(rank: int, chars: int = 100, db_id: str = "lex-id") -> Document:
    """Doc como sairia de `_normalize_lexical_match_doc` + `_rrf_fuse`: sem
    `similarity`, com `lexical_rank`."""
    return Document(
        page_content="y" * chars,
        metadata={"db_id": db_id, "lexical_rank": rank},
    )


class TestBuildLexicalQuery:
    def test_short_domain_acronyms_survive(self, service):
        """Diferente do antigo bônus de reranking (limiar >4), siglas
        curtas do domínio (KV, FIS, RPL) precisam sobreviver — são
        exatamente os termos que esta busca existe para capturar."""
        query = service._build_lexical_query("Qual o KV e o FIS do RPL?", "")
        assert "kv" in query
        assert "fis" in query
        assert "rpl" in query

    def test_decimal_values_survive_as_single_token(self, service):
        """'64.10'/'1.26' não podem virar dois tokens separados ('64' e
        '10') — perderiam o valor exato que a busca léxica existe para
        casar."""
        query = service._build_lexical_query("Qual tratamento teve 64.10 de RPL?", "")
        assert "64.10" in query

    def test_terms_joined_by_or_not_and(self, service):
        query = service._build_lexical_query("tratamento crescimento", "")
        assert " | " in query
        assert " & " not in query

    def test_stopwords_removed(self, service):
        query = service._build_lexical_query("qual é o tratamento", "")
        assert "qual" not in query.split(" | ")
        assert "tratamento" in query

    def test_accents_stripped_via_nfkd(self, service):
        query = service._build_lexical_query("índice de proteção", "")
        assert "indice" in query
        assert "protecao" in query

    def test_empty_question_returns_empty_query(self, service):
        query = service._build_lexical_query("é o de", "")
        assert query == ""


class TestRrfFuse:
    def test_docs_in_both_lists_combine_scores(self, service):
        v = _vector_doc(0.7, db_id="shared")
        l = _lexical_doc(0, db_id="shared")
        fused = service._rrf_fuse([v], [l], rrf_k=60)
        assert len(fused) == 1
        # O doc vetorial original é preservado (com similarity real), não
        # substituído pela versão léxica sem similarity.
        assert fused[0].metadata.get("similarity") == 0.7

    def test_lexical_only_doc_gets_lexical_rank_and_no_similarity(self, service):
        v = _vector_doc(0.7, db_id="vec-only")
        l = _lexical_doc(0, db_id="lex-only")
        fused = service._rrf_fuse([v], [l], rrf_k=60)
        lex_doc = next(d for d in fused if d.metadata.get("db_id") == "lex-only")
        assert "lexical_rank" in lex_doc.metadata
        assert "similarity" not in lex_doc.metadata

    def test_top_ranked_lexical_only_doc_can_outrank_weak_vector_doc(self, service):
        """Um doc encontrado só pela via léxica, mas no topo do rank
        léxico, pode superar um doc vetorial de rank baixo no score
        fundido (RRF usa só a POSIÇÃO em cada lista, não o valor do score
        — dois docs no mesmo rank empatam) — esse é o comportamento
        pretendido da fusão. A segurança do piso de recusa não depende de
        impedir isso; depende de `_select_context_docs` nunca usar a
        posição fundida para a decisão de recusa (ver classe abaixo)."""
        vector_docs = [_vector_doc(0.9 - i * 0.05, db_id=f"vec-{i}") for i in range(5)]
        weak_vector = vector_docs[-1]  # último rank da lista vetorial
        top_lexical = _lexical_doc(0, db_id="top-lexical")
        fused = service._rrf_fuse(vector_docs, [top_lexical], rrf_k=60)
        rank_of_lexical = next(i for i, d in enumerate(fused) if d.metadata.get("db_id") == "top-lexical")
        rank_of_weak_vector = next(i for i, d in enumerate(fused) if d.metadata.get("db_id") == weak_vector.metadata["db_id"])
        assert rank_of_lexical < rank_of_weak_vector

    def test_empty_lexical_list_preserves_vector_order(self, service):
        docs = [_vector_doc(0.9, db_id="a"), _vector_doc(0.8, db_id="b")]
        fused = service._rrf_fuse(docs, [], rrf_k=60)
        assert [d.metadata["db_id"] for d in fused] == ["a", "b"]


class TestRefusalFloorIgnoresFusedRank:
    """Task 4.3: a fusão RRF nunca deve afetar a decisão de recusa —
    sempre o cosseno bruto do melhor candidato vetorial."""

    def test_lexical_only_doc_at_top_does_not_bypass_refusal(self, service):
        """Cenário central do risco: um doc léxico-only promovido ao topo
        do ranking fundido, mas o melhor cosseno REAL está abaixo do piso
        de recusa — precisa recusar mesmo assim."""
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        ranked = [
            _lexical_doc(0, db_id="top-of-fused-rank"),  # topo do ranking fundido
            _vector_doc(below_floor, db_id="only-vector-candidate"),
        ]
        selected, reason = service._select_context_docs(ranked)
        assert selected == []
        assert reason == "refused"

    def test_lexical_only_doc_at_top_with_good_vector_candidate_does_not_refuse(self, service):
        """Inverso: o cosseno real está acima do piso (mesmo não sendo o
        topo do ranking fundido) — não deve recusar."""
        above_floor = REFUSAL_FLOOR_SIMILARITY + 0.1
        ranked = [
            _lexical_doc(0, db_id="top-of-fused-rank"),
            _vector_doc(above_floor, db_id="genuine-vector-candidate"),
        ] + [_vector_doc(above_floor - 0.01, db_id=f"filler-{i}") for i in range(10)]
        selected, reason = service._select_context_docs(ranked)
        assert selected != []
        assert reason != "refused"

    def test_context_absolute_floor_does_not_exclude_lexical_only_docs(self, service):
        """Task 4.2: `CONTEXT_ABSOLUTE_FLOOR` só filtra docs vetoriais —
        um doc léxico-only nunca é excluído por não ter cosseno."""
        above_floor = REFUSAL_FLOOR_SIMILARITY + 0.1
        ranked = (
            [_vector_doc(above_floor, db_id="top-vector")]
            + [_lexical_doc(i, db_id=f"lex-{i}") for i in range(5)]
            + [_vector_doc(above_floor - 0.001, db_id=f"filler-{i}") for i in range(10)]
        )
        selected, _ = service._select_context_docs(ranked)
        selected_ids = {d.metadata.get("db_id") for d in selected}
        assert any(f"lex-{i}" in selected_ids for i in range(5))

    def test_pure_vector_behavior_unchanged_when_no_lexical_docs_present(self, service):
        """Quando a busca híbrida está desligada, `ranked` nunca contém
        docs léxico-only — o comportamento precisa ser idêntico ao de
        antes desta change (regressão de `restore-rag-answer-quality`)."""
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        ranked = [_vector_doc(below_floor, db_id="only-candidate")]
        selected, reason = service._select_context_docs(ranked)
        assert selected == []
        assert reason == "refused"


class TestHybridWiringInRetrieveDocsViaRpc:
    """`_retrieve_docs_via_rpc`: `HYBRID_SEARCH_ENABLED` liga/desliga a
    segunda chamada RPC sem exigir mudança de código (spec: 'Hybrid
    retrieval can be disabled without a code change')."""

    def _mock_vector_match(self, similarity: float, db_id: str = "v-1"):
        return {"id": db_id, "content": "conteudo vetorial", "similarity": similarity, "metadata": {}}

    def test_disabled_never_calls_lexical_rpc(self, service):
        mock_lexical = MagicMock(return_value=[])
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(0.9)]), \
             patch.object(service, "_search_lexical_rpc", mock_lexical), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", False):
            service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        mock_lexical.assert_not_called()

    def test_enabled_calls_lexical_rpc(self, service):
        mock_lexical = MagicMock(return_value=[])
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(0.9)]), \
             patch.object(service, "_search_lexical_rpc", mock_lexical), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", True):
            service._retrieve_docs_via_rpc("pergunta sobre RPL", k=5, use_llm_expansion=False)
        mock_lexical.assert_called_once()


class TestDiscriminativeLexicalCoverage:
    """`_has_discriminative_lexical_match`: segundo sinal de recusa,
    independente do cosseno (grupo 5)."""

    def _mock_doc_freq_rpc(self, service, rows):
        response = MagicMock()
        response.data = rows
        return patch.object(service.supabase_admin, "rpc", return_value=MagicMock(execute=MagicMock(return_value=response)))

    def test_discriminative_term_present_returns_true(self, service):
        with self._mock_doc_freq_rpc(service, [{"term": "rpl", "doc_count": 2, "total_docs": 124}]):
            assert service._has_discriminative_lexical_match("Qual o RPL?", "") is True

    def test_only_generic_terms_returns_false(self, service):
        with self._mock_doc_freq_rpc(service, [{"term": "tilapia", "doc_count": 80, "total_docs": 124}]):
            assert service._has_discriminative_lexical_match("Sobre tilapia", "") is False

    def test_term_absent_from_corpus_returns_false(self, service):
        """Frequência 0 é tecnicamente <= 20%, mas um termo ausente não
        'casa' com nada — não pode contar como match positivo."""
        with self._mock_doc_freq_rpc(service, [{"term": "xyzforadocorpus", "doc_count": 0, "total_docs": 124}]):
            assert service._has_discriminative_lexical_match("O que é xyzforadocorpus?", "") is False

    def test_no_terms_to_check_defaults_to_true(self, service):
        """Pergunta sem termos de conteúdo (só stopwords) — postura
        conservadora: não bloqueia sem termos para checar."""
        assert service._has_discriminative_lexical_match("é o de", "") is True

    def test_rpc_failure_defaults_to_true(self, service):
        """Falha de infraestrutura não deve, sozinha, causar uma recusa —
        este é um sinal complementar, não a fonte primária de recusa."""
        with patch.object(service.supabase_admin, "rpc", side_effect=Exception("conexão falhou")):
            assert service._has_discriminative_lexical_match("Qual o RPL?", "") is True


class TestIntermediateZoneLexicalSignalWiring:
    """`_retrieve_docs_via_rpc`: o sinal léxico só age na zona
    intermediária (entre o piso de recusa e o limiar de confiança alta), e
    só quando a busca híbrida está ligada — nunca "resgata" uma recusa por
    cosseno nem enfraquece uma confiança já alta."""

    def _mock_vector_match(self, similarity: float, db_id: str = "v-1"):
        return {
            "id": db_id,
            "content": "conteudo vetorial de teste " * 20,
            "similarity": similarity,
            "metadata": {},
        }

    def _intermediate_score(self, service) -> float:
        from app.utils.rag_config import PRIMARY_RPC_SIMILARITY_THRESHOLD
        return (REFUSAL_FLOOR_SIMILARITY + PRIMARY_RPC_SIMILARITY_THRESHOLD) / 2

    def test_intermediate_zone_no_lexical_match_refuses(self, service):
        intermediate = self._intermediate_score(service)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(intermediate)]), \
             patch.object(service, "_search_lexical_rpc", return_value=[]), \
             patch.object(service, "_has_discriminative_lexical_match", return_value=False), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", True):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert docs == []

    def test_intermediate_zone_with_lexical_match_does_not_refuse(self, service):
        intermediate = self._intermediate_score(service)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(intermediate)]), \
             patch.object(service, "_search_lexical_rpc", return_value=[]), \
             patch.object(service, "_has_discriminative_lexical_match", return_value=True), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", True):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert len(docs) > 0

    def test_high_confidence_zone_ignores_lexical_signal(self, service):
        """Acima do limiar de confiança alta, o sinal léxico nem é
        consultado — um match ausente não pode enfraquecer uma confiança
        já alta baseada em cosseno."""
        from app.utils.rag_config import PRIMARY_RPC_SIMILARITY_THRESHOLD
        strong = PRIMARY_RPC_SIMILARITY_THRESHOLD + 0.05
        mock_lexical_check = MagicMock(return_value=False)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(strong)]), \
             patch.object(service, "_search_lexical_rpc", return_value=[]), \
             patch.object(service, "_has_discriminative_lexical_match", mock_lexical_check), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", True):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert len(docs) > 0
        mock_lexical_check.assert_not_called()

    def test_disabled_hybrid_ignores_lexical_signal(self, service):
        """Sem busca híbrida ligada, o sinal léxico nunca é consultado,
        mesmo na zona intermediária."""
        intermediate = self._intermediate_score(service)
        mock_lexical_check = MagicMock(return_value=False)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[self._mock_vector_match(intermediate)]), \
             patch.object(service, "_has_discriminative_lexical_match", mock_lexical_check), \
             patch("app.services.rag_service.HYBRID_SEARCH_ENABLED", False):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert len(docs) > 0
        mock_lexical_check.assert_not_called()
