# CAMINHO: backend/tests/test_verify_numeric.py
"""Testes do nó `verify_numeric` (`add-rag-self-correction-loop`, grupo 1).

Verificação determinística (regex, sem LLM) de que todo número citado na
resposta final aparece no contexto — sinal de custo zero contra o pior
modo de falha num corpus inteiro quantitativo: um valor com aparência de
dado real que não está em lugar nenhum do texto fornecido.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service


@pytest.fixture
def service():
    return get_rag_service()


def _mock_utility_sufficient():
    """`grade_context` roda entre `retrieve` e `generate` em todo
    `get_answer`, chamando `llm_utility` diretamente — sem mockar isso,
    estes testes fariam uma chamada real à API a cada execução."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="SUFFICIENT")
    return mock


def _mock_doc(content: str) -> Document:
    return Document(
        page_content=content,
        metadata={
            "similarity": 0.9,
            "db_id": "id-1",
            "original_file_name": "doc.pdf",
            "original_file_id": "file-1",
            "page": 1,
        },
    )


class TestVerifyNumericGrounded:
    """Todos os números da resposta aparecem no contexto → segue sem
    regenerar (1 única chamada de geração)."""

    def test_all_numbers_present_does_not_regenerate(self, service):
        context_doc = _mock_doc(
            "O tratamento PRO+MOS apresentou 64,10% de proteção relativa, "
            "contra 21,02% do MOS isolado. " * 10
        )
        response = MagicMock()
        response.content = "O tratamento PRO+MOS apresentou 64,10% de proteção relativa, contra 21,02% do MOS."
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = response

        with patch.object(service, "llm_generation", mock_llm), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[context_doc]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual tratamento teve maior RPL?", [])

        assert result.answer == response.content
        assert mock_llm.invoke.call_count == 1


class TestVerifyNumericUnsupportedTriggersRegeneration:
    """Número inventado (ausente do contexto) → regenera exatamente 1 vez
    com instrução de correção citando o valor específico."""

    def test_one_invented_number_regenerates_once(self, service):
        context_doc = _mock_doc(
            "O tratamento PRO+MOS apresentou 64,10% de proteção relativa. " * 10
        )
        bad_response = MagicMock()
        bad_response.content = "O tratamento PRO+MOS apresentou 99,99% de proteção relativa."
        corrected_response = MagicMock()
        corrected_response.content = "O tratamento PRO+MOS apresentou 64,10% de proteção relativa."
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [bad_response, corrected_response]

        with patch.object(service, "llm_generation", mock_llm), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[context_doc]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual a proteção relativa do PRO+MOS?", [])

        assert mock_llm.invoke.call_count == 2
        assert result.answer == corrected_response.content

        # A instrução de correção da 2ª chamada precisa citar o valor ofensor.
        second_call_messages = mock_llm.invoke.call_args_list[1].args[0]
        system_message = second_call_messages[0].content
        assert "99.99%" in system_message or "99,99%" in system_message

    def test_regenerated_answer_still_unsupported_is_accepted_without_third_call(self, service):
        """Segunda falha é aceita sem 3ª tentativa — pode ser aritmética
        derivada legitimamente do contexto, não uma invenção (design.md)."""
        context_doc = _mock_doc(
            "O tratamento PRO+MOS apresentou 64,10% de proteção relativa. " * 10
        )
        bad_response = MagicMock()
        bad_response.content = "O tratamento PRO+MOS apresentou 99,99% de proteção relativa."
        still_bad_response = MagicMock()
        still_bad_response.content = "O tratamento PRO+MOS apresentou 88,88% de proteção relativa."
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [bad_response, still_bad_response]

        with patch.object(service, "llm_generation", mock_llm), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[context_doc]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual a proteção relativa do PRO+MOS?", [])

        assert mock_llm.invoke.call_count == 2
        assert result.answer == still_bad_response.content


class TestVerifyNumericRefusalSkipsVerification:
    """Recusa (sentinela ou contexto insuficiente) não tem números para
    verificar — não deve disparar nenhuma chamada extra."""

    def test_refusal_via_insufficient_context_skips_verification(self, service):
        mock_llm = MagicMock()

        with patch.object(service, "llm_generation", mock_llm), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[]):
            result = service.get_answer("Pergunta totalmente fora do escopo", [])

        mock_llm.invoke.assert_not_called()
        assert result.sources == []

    def test_refusal_via_sentinel_skips_verification(self, service):
        context_doc = _mock_doc("Conteúdo científico de teste sobre tilápia. " * 20)
        sentinel_response = MagicMock()
        sentinel_response.content = service.NO_ANSWER_SENTINEL
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = sentinel_response

        with patch.object(service, "llm_generation", mock_llm), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[context_doc]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            service.get_answer("Pergunta fora do escopo mas com contexto parcial", [])

        assert mock_llm.invoke.call_count == 1
