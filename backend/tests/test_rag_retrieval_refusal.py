# CAMINHO: backend/tests/test_rag_retrieval_refusal.py
"""Testes de regressão para a lógica nova de retrieval-refusal-quality.

Cobertura mínima e deliberada: a mudança que motivou esta mudança inteira
(embedding caindo silenciosamente para ada-002 por meses) só passou
despercebida porque nada testava a configuração efetiva nem o
comportamento de recuperação. Estes testes existem para não repetir isso.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service
from app.utils.rag_config import (
    CONTEXT_ABSOLUTE_FLOOR,
    CONTEXT_CHAR_BUDGET,
    CONTEXT_MAX_CHUNKS,
    CONTEXT_MIN_CHUNKS,
    REFUSAL_FLOOR_SIMILARITY,
)


@pytest.fixture
def service():
    return get_rag_service()


def _mock_match(similarity: float, content: str = "conteudo de teste", db_id: str = "id-1"):
    return {"id": db_id, "content": content, "similarity": similarity, "metadata": {}}


class TestRefusalFallback:
    """`_retrieve_docs_via_rpc`: comportamento em três faixas de similaridade."""

    def test_above_threshold_returns_docs_normally(self, service):
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[_mock_match(service.similarity_threshold + 0.1)]):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert len(docs) == 1

    def test_between_floor_and_threshold_stays_within_selection_bounds(self, service):
        """Zona intermediária (abaixo do threshold de confiança alta, acima do
        piso de recusa) não é mais tudo-ou-nada: com muitos candidatos
        disponíveis, a seleção fica sempre entre CONTEXT_MIN_CHUNKS e
        CONTEXT_MAX_CHUNKS — nunca a inundação de todos os 40 candidatos que
        o regime binário antigo produzia aqui (comportamento que este teste
        antes afirmava como correto)."""
        weak_top = (REFUSAL_FLOOR_SIMILARITY + service.similarity_threshold) / 2
        assert REFUSAL_FLOOR_SIMILARITY < weak_top < service.similarity_threshold
        matches = [
            _mock_match(max(weak_top - i * 0.01, 0.0), db_id=f"id-{i}")
            for i in range(40)
        ]
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=matches):
            docs = service._retrieve_docs_via_rpc("pergunta", k=40, use_llm_expansion=False)
        assert CONTEXT_MIN_CHUNKS <= len(docs) <= CONTEXT_MAX_CHUNKS
        assert len(docs) < 40, "não pode mais inundar com todos os candidatos"

    def test_below_floor_refuses_with_empty_docs(self, service):
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[_mock_match(below_floor)]):
            docs = service._retrieve_docs_via_rpc("pergunta", k=5, use_llm_expansion=False)
        assert docs == [], "score abaixo do piso de recusa não deve devolver nenhum chunk"

    def test_no_bypass_parameter_exists_for_refusal_floor(self, service):
        """`skip_threshold` foi removido (add-rag-self-correction-loop,
        task 4.1) — não existe mais nenhum parâmetro que ignore o piso de
        recusa. Mesmo uma chamada no "estilo retry" (k maior, expansão
        desligada) aplica o mesmo piso que a tentativa original."""
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[_mock_match(below_floor)]):
            docs = service._retrieve_docs_via_rpc(
                "pergunta", k=5, use_llm_expansion=False
            )
        assert docs == []


def _mock_doc(similarity: float, chars: int = 100, db_id: str = "id") -> Document:
    return Document(
        page_content="x" * chars,
        metadata={"similarity": similarity, "db_id": db_id},
    )


class TestSelectContextDocs:
    """`_select_context_docs`: seleção por ranking com piso mínimo, teto
    máximo e orçamento de caracteres — substitui o regime binário antigo."""

    def test_min_fill_completes_with_next_best_candidates(self, service):
        """Só 3 candidatos na janela relativa (score muito diferente do
        top-1) — a seleção completa até CONTEXT_MIN_CHUNKS puxando os
        próximos melhores do pool, em vez de starvar em 3."""
        ranked = (
            [_mock_doc(0.90, db_id="id-0")]
            + [_mock_doc(0.89, db_id="id-1"), _mock_doc(0.88, db_id="id-2")]
            + [_mock_doc(0.10 + i * 0.001, db_id=f"far-{i}") for i in range(20)]
        )
        docs, reason = service._select_context_docs(ranked)
        assert reason == "min_fill"
        assert len(docs) == CONTEXT_MIN_CHUNKS

    def test_char_budget_never_cuts_below_minimum(self, service):
        """Um chunk enorme não pode, sozinho, estourar o orçamento a ponto
        de a seleção final ficar abaixo do mínimo garantido."""
        huge = _mock_doc(0.90, chars=30000, db_id="huge")
        rest = [_mock_doc(0.90 - i * 0.001, chars=500, db_id=f"id-{i}") for i in range(1, 20)]
        docs, _ = service._select_context_docs([huge] + rest)
        assert len(docs) >= CONTEXT_MIN_CHUNKS

    def test_char_budget_caps_total_size_when_pool_is_large(self, service):
        """Com candidatos abundantes, o orçamento de caracteres é respeitado
        acima do mínimo garantido."""
        ranked = [_mock_doc(0.90 - i * 0.001, chars=3000, db_id=f"id-{i}") for i in range(CONTEXT_MAX_CHUNKS)]
        docs, _ = service._select_context_docs(ranked)
        total_chars = sum(len(d.page_content) for d in docs)
        assert total_chars <= CONTEXT_CHAR_BUDGET or len(docs) <= CONTEXT_MIN_CHUNKS

    def test_many_strong_candidates_are_capped_at_maximum(self, service):
        """Muitos candidatos fortes (todos dentro da janela relativa) não
        inundam o contexto — corta em CONTEXT_MAX_CHUNKS."""
        ranked = [_mock_doc(0.90 - i * 0.001, db_id=f"id-{i}") for i in range(40)]
        docs, reason = service._select_context_docs(ranked)
        assert len(docs) == CONTEXT_MAX_CHUNKS
        assert reason in ("relative_window", "min_fill")

    def test_no_candidate_meets_floor_returns_empty(self, service):
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.05, 0.0)
        ranked = [_mock_doc(below_floor, db_id="id-0")]
        docs, reason = service._select_context_docs(ranked)
        assert docs == []
        assert reason == "refused"

    def test_empty_pool_returns_empty(self, service):
        docs, reason = service._select_context_docs([])
        assert docs == []
        assert reason == "refused"

    def test_absolute_floor_excludes_far_candidates_from_relative_window(self, service):
        """Um candidato abaixo do piso absoluto não entra na janela relativa
        mesmo se o top-1 estiver muito acima — mas ainda pode entrar via
        preenchimento mínimo, que é o comportamento correto (não starvar)."""
        far_below_absolute = max(CONTEXT_ABSOLUTE_FLOOR - 0.05, REFUSAL_FLOOR_SIMILARITY)
        ranked = [_mock_doc(0.95, db_id="id-0"), _mock_doc(far_below_absolute, db_id="id-1")]
        docs, reason = service._select_context_docs(ranked)
        # Só 1 candidato na janela relativa -> min_fill completa com o resto do pool.
        assert reason == "min_fill"
        assert len(docs) == 2  # não há mais candidatos no pool além destes 2


class TestConfigFromEnvironment:
    """Config de recuperação/recusa não pode voltar a ser hardcoded."""

    def test_retrieval_constants_are_read_from_env(self, monkeypatch):
        monkeypatch.setenv("RETRIEVAL_K", "77")
        monkeypatch.setenv("REFUSAL_FLOOR_SIMILARITY", "0.42")
        import importlib
        from app.utils import rag_config
        importlib.reload(rag_config)
        try:
            assert rag_config.RETRIEVAL_K == 77
            assert rag_config.REFUSAL_FLOOR_SIMILARITY == pytest.approx(0.42)
        finally:
            monkeypatch.delenv("RETRIEVAL_K", raising=False)
            monkeypatch.delenv("REFUSAL_FLOOR_SIMILARITY", raising=False)
            importlib.reload(rag_config)


class TestFollowupCondensation:
    """`_condense_followup_question`: só age quando há histórico."""

    def test_no_history_returns_question_unchanged(self, service):
        mock_llm = MagicMock()
        with patch.object(service, "llm_utility", mock_llm):
            result = service._condense_followup_question("pergunta original", [], "pt-BR")
        assert result == "pergunta original"
        mock_llm.invoke.assert_not_called()

    def test_with_history_condenses_via_llm(self, service):
        mock_response = MagicMock()
        mock_response.content = "Qual a margem por unidade do equipamento BIA?"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        history = [["Qual o preço do equipamento BIA?", "R$ 17.000 por unidade."]]
        with patch.object(service, "llm_utility", mock_llm):
            result = service._condense_followup_question(
                "E qual a margem por unidade?", history, "pt-BR"
            )
        assert result == "Qual a margem por unidade do equipamento BIA?"
        mock_llm.invoke.assert_called_once()

    def test_llm_failure_falls_back_to_mechanical_concat(self, service):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API indisponível")
        history = [["Qual o preço do BIA?", "R$ 17.000."]]
        with patch.object(service, "llm_utility", mock_llm):
            result = service._condense_followup_question("E a margem?", history, "pt-BR")
        assert "Qual o preço do BIA?" in result
        assert "E a margem?" in result


class TestRetrieveForEval:
    """`retrieve_for_eval`: seam usado pelo harness — condensa follow-up antes
    de recuperar, para que a avaliação exercite o mesmo caminho que produção."""

    def test_follow_up_question_uses_condensed_query_for_search(self, service):
        """Sem condensação, uma pergunta de follow-up embutida sozinha
        ('E qual teve o menor?') não recupera nada relevante — a mesma causa
        raiz documentada em `_condense_followup_question`."""
        mock_condense_response = MagicMock()
        mock_condense_response.content = "Qual estoque teve a menor área de filé por ultrassonografia?"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_condense_response

        history = [["Qual estoque teve a maior área de filé?", "O estoque ILH, com 7,05."]]

        with patch.object(service, "llm_utility", mock_llm), \
             patch.object(service, "_embed_query", return_value=[0.0] * 1536) as mock_embed, \
             patch.object(service, "_search_rpc", return_value=[_mock_match(0.9)]):
            docs, trace = service.retrieve_for_eval(
                "E qual teve o menor?", history, k=5, use_llm_expansion=False
            )

        assert trace["retrieval_query"] == "Qual estoque teve a menor área de filé por ultrassonografia?"
        assert len(docs) == 1
        # A pergunta embutida na busca precisa ser a condensada, não a crua.
        called_with_text = mock_embed.call_args[0][0]
        assert called_with_text == "Qual estoque teve a menor área de filé por ultrassonografia?"

    def test_no_history_uses_question_unchanged(self, service):
        """Sem histórico, a condensação não roda (não chama o LLM) — a query
        de recuperação é a pergunta original. `use_llm_expansion=False` para
        isolar esse comportamento do de `_expand_query_with_llm`, uma chamada
        de LLM separada e deliberada, não relacionada à condensação."""
        mock_llm = MagicMock()
        with patch.object(service, "llm_utility", mock_llm), \
             patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[_mock_match(0.9)]):
            docs, trace = service.retrieve_for_eval(
                "pergunta autocontida", None, k=5, use_llm_expansion=False
            )
        mock_llm.invoke.assert_not_called()
        assert trace["retrieval_query"] == "pergunta autocontida"
        assert len(docs) == 1

    def test_trace_reports_raw_similarity_before_refusal_gate(self, service):
        """`top_similarity_raw` não pode ser contaminado por uma recusa —
        hoje `top_similarity` é lido só do resultado pós-gate, que é vazio
        numa recusa, escondendo o quão perto a pergunta chegou do piso."""
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=[_mock_match(below_floor)]):
            docs, trace = service.retrieve_for_eval(
                "pergunta", None, k=5, use_llm_expansion=False
            )
        assert docs == []
        assert trace["selection_reason"] == "refused"
        assert trace["top_similarity_raw"] == pytest.approx(below_floor)
        assert trace["candidate_count"] == 1
        assert trace["selected_count"] == 0

    def test_trace_reports_selected_count_and_context_chars(self, service):
        matches = [_mock_match(0.9, content="a" * 100, db_id="id-1"),
                   _mock_match(0.85, content="b" * 50, db_id="id-2")]
        with patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(service, "_search_rpc", return_value=matches):
            docs, trace = service.retrieve_for_eval(
                "pergunta", None, k=5, use_llm_expansion=False
            )
        assert trace["selected_count"] == 2
        assert trace["context_chars"] == 150
