# CAMINHO: backend/tests/test_reformulation_flow.py
"""Testes do fluxo de reformulação (`add-rag-self-correction-loop`, grupo 4).

`grade_context` retornando `insufficient` reformula a query condensada e
recupera de novo (`reformulate_and_retrieve`), no máximo 1 vez — substitui
`retrieve_retry`, que ignorava o piso de recusa (`skip_threshold=True`).
A nova tentativa passa pelo MESMO `_select_context_docs`/piso de recusa da
original: nunca resgata com contexto que a tentativa inicial já teria
recusado.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service
from app.utils.rag_config import REFUSAL_FLOOR_SIMILARITY


@pytest.fixture
def service():
    return get_rag_service()


def _mock_doc(similarity: float = 0.9, content: str = None) -> Document:
    return Document(
        page_content=content or "Conteúdo científico de teste sobre tilápia. " * 20,
        metadata={
            "similarity": similarity,
            "db_id": "id-1",
            "original_file_name": "doc.pdf",
            "original_file_id": "file-1",
            "page": 1,
        },
    )


def _mock_generation():
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="O ganho de peso médio foi registrado ao longo do experimento."
    )
    return mock


class TestReformulationSucceeds:
    def test_insufficient_then_sufficient_reformulation_generates_answer(self, service):
        """1ª recuperação: contexto encontrado, mas `grade_context` julga
        `insufficient`. Reformulação: nova recuperação, `grade_context`
        julga `sufficient` desta vez → gera resposta."""
        mock_utility = MagicMock()
        mock_utility.invoke.side_effect = [
            MagicMock(content="INSUFFICIENT"),  # 1ª avaliação
            MagicMock(content="SUFFICIENT"),    # 2ª avaliação, pós-reformulação
        ]
        mock_generation = _mock_generation()
        mock_retrieve = MagicMock(return_value=[_mock_doc()])

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", mock_generation), \
             patch.object(service, "_retrieve_docs_via_rpc", mock_retrieve), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual o ganho de peso médio?", [])

        assert mock_utility.invoke.call_count == 2
        assert mock_retrieve.call_count == 2
        assert mock_generation.invoke.call_count == 1
        assert result.answer == "O ganho de peso médio foi registrado ao longo do experimento."

    def test_reformulation_uses_condensed_retrieval_query_not_raw_question(self, service):
        """Task 4.3: a reformulação usa `retrieval_query` (condensada),
        não `state["question"]` cru."""
        mock_utility = MagicMock()
        mock_utility.invoke.side_effect = [
            MagicMock(content="INSUFFICIENT"),
            MagicMock(content="SUFFICIENT"),
        ]
        mock_retrieve = MagicMock(return_value=[_mock_doc()])

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", mock_retrieve), \
             patch.object(service, "_expand_query_for_retry", side_effect=lambda q: f"EXPANDED[{q}]") as mock_expand, \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            service.get_answer("Qual o ganho de peso médio?", [])

        # `_expand_query_for_retry` deve ter recebido a `retrieval_query`
        # (igual à pergunta original aqui, sem histórico) — não uma pergunta
        # crua de follow-up.
        mock_expand.assert_called_once()
        second_retrieve_call = mock_retrieve.call_args_list[1]
        assert second_retrieve_call.args[0] == "EXPANDED[Qual o ganho de peso médio?]"


class TestReformulationExhausted:
    def test_insufficient_twice_refuses_without_third_attempt(self, service):
        """1ª e 2ª (reformulada) avaliações ambas `insufficient` → recusa,
        sem 3ª tentativa. `llm_generation` nunca é chamado (recusa é
        gratuita, via `insufficient_context`)."""
        mock_utility = MagicMock()
        mock_utility.invoke.side_effect = [
            MagicMock(content="INSUFFICIENT"),
            MagicMock(content="INSUFFICIENT"),
        ]
        mock_generation = _mock_generation()
        mock_retrieve = MagicMock(return_value=[_mock_doc()])

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", mock_generation), \
             patch.object(service, "_retrieve_docs_via_rpc", mock_retrieve), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Pergunta ambígua fora do escopo", [])

        assert mock_utility.invoke.call_count == 2
        assert mock_retrieve.call_count == 2
        mock_generation.invoke.assert_not_called()
        assert result.sources == []
        assert result.answer in (
            service._build_refusal_message("pt-BR"),
            service._build_refusal_message("en"),
        )

    def test_reformulated_candidate_below_refusal_floor_never_bypasses(self, service):
        """A tentativa reformulada nunca ignora o piso de recusa — se o
        melhor candidato reformulado fica abaixo dele, `_select_context_docs`
        recusa (mesmo comportamento da tentativa original, sem parâmetro
        de bypass)."""
        below_floor = max(REFUSAL_FLOOR_SIMILARITY - 0.1, 0.0)
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content="INSUFFICIENT")
        mock_generation = _mock_generation()

        # 1ª recuperação (via `_search_rpc`/`_embed_query`, não mockando
        # `_retrieve_docs_via_rpc` diretamente aqui) precisa também não
        # atingir o piso, senão a 1ª chamada teria contexto.
        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", mock_generation), \
             patch.object(service, "_embed_query", return_value=[0.0] * 1536), \
             patch.object(
                 service, "_search_rpc",
                 return_value=[{
                     "id": "id-1", "content": "conteúdo abaixo do piso",
                     "similarity": below_floor, "metadata": {"original_file_name": "doc.pdf"},
                 }],
             ):
            result = service.get_answer("Pergunta fora do escopo", [])

        mock_generation.invoke.assert_not_called()
        assert result.sources == []
