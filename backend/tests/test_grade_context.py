# CAMINHO: backend/tests/test_grade_context.py
"""Testes do nó `grade_context` (`add-rag-self-correction-loop`, grupo 2 —
modo observação).

Julga suficiência semântica do contexto ANTES de gerar, mas ainda não
altera o fluxo do grafo (isso é o grupo 4, que substitui `retrieve_retry`).
Estes testes travam: (a) o nó chama `llm_utility` com pergunta+contexto,
(b) o parsing dos 3 estados possíveis, (c) que o resultado não afeta o
fluxo em modo observação, (d) que contexto já vazio pula a chamada.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service


@pytest.fixture
def service():
    return get_rag_service()


def _input_state(question: str, question_type: str = "conceptual", history: list | None = None) -> dict:
    """Espelha o `input_state` montado por `get_answer` — necessário aqui
    porque `context_sufficiency` só é observável no estado final do grafo,
    não no contrato público de `AnswerResult`."""
    return {
        "question": question,
        "context": "",
        "answer": "",
        "evaluation": "",
        "retry_count": 0,
        "language": "pt-BR",
        "history": history or [],
        "question_type": question_type,
        "insufficient_context": False,
        "source_docs": [],
        "context_confidence": "strong",
        "effective_type": question_type,
        "unsupported_numbers": [],
        "numeric_regen_count": 0,
        "context_sufficiency": "",
        "retrieval_query": "",
        "reformulation_count": 0,
    }


def _mock_doc() -> Document:
    return Document(
        page_content="Conteúdo científico de teste sobre tilápia. " * 20,
        metadata={
            "similarity": 0.9,
            "db_id": "id-1",
            "original_file_name": "doc.pdf",
            "original_file_id": "file-1",
            "page": 1,
        },
    )


def _mock_generation():
    # Precisa mencionar um termo significativo da pergunta usada nos testes
    # ("ganho de peso médio") para passar em `_is_answer_relevant` — senão
    # `evaluate` marca LOW_QUALITY e o grafo dispara um retry real, inflando
    # `call_count` por um motivo alheio ao que estes testes verificam.
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="O ganho de peso médio foi registrado ao longo do experimento."
    )
    return mock


class TestGradeContextCallsUtilityModel:
    def test_calls_llm_utility_with_question_and_context(self, service):
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content="SUFFICIENT")

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(_input_state("Qual o ganho de peso médio?"))

        mock_utility.invoke.assert_called_once()
        messages = mock_utility.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "Qual o ganho de peso médio?" in human_content
        assert "Conteúdo científico de teste" in human_content
        assert result["context_sufficiency"] == "sufficient"


class TestGradeContextUsesCondensedFollowupQuery:
    """Regressão encontrada na calibração (task 2.3/3): `grade_context`
    deve julgar contra `retrieval_query` (condensada com histórico por
    `retrieve`), não `state["question"]` cru. Uma pergunta de follow-up
    como "E qual teve o menor?" é ininteligível sozinha — a 1ª calibração
    julgava as 4 perguntas de follow-up do golden set como `insufficient`
    mesmo com o contexto certo, só por causa disso (31.4% → 97.1% de
    acurácia geral após a correção)."""

    def test_grades_against_condensed_query_not_raw_followup(self, service):
        condense_response = MagicMock(
            content="Qual estoque teve a menor área de filé por ultrassonografia?"
        )
        grade_response = MagicMock(content="SUFFICIENT")
        mock_utility = MagicMock()
        mock_utility.invoke.side_effect = [condense_response, grade_response]

        history = [["Qual estoque teve a maior área de filé?", "O estoque ILH, com 7,05."]]

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(
                _input_state("E qual teve o menor?", question_type="quantitative", history=history)
            )

        assert result["context_sufficiency"] == "sufficient"
        assert mock_utility.invoke.call_count == 2

        grade_call_messages = mock_utility.invoke.call_args_list[1].args[0]
        human_content = grade_call_messages[1].content
        assert "área de filé por ultrassonografia" in human_content
        assert "E qual teve o menor?" not in human_content


class TestGradeContextParsesVerdict:
    @pytest.mark.parametrize(
        "raw_response,expected",
        [
            ("SUFFICIENT", "sufficient"),
            ("sufficient", "sufficient"),
            ("PARTIAL", "partial"),
            ("partial", "partial"),
            ("INSUFFICIENT", "insufficient"),
            ("insufficient", "insufficient"),
            ("  SUFFICIENT.  ", "sufficient"),
        ],
    )
    def test_parses_expected_verdicts(self, service, raw_response, expected):
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content=raw_response)

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(_input_state("Qual o ganho de peso médio?"))

        assert result["context_sufficiency"] == expected

    def test_unexpected_response_defaults_to_partial(self, service):
        """Postura conservadora: uma resposta fora do formato esperado não
        deve ser tratada como `sufficient` sem sinal claro."""
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content="I cannot determine this.")

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(_input_state("Qual o ganho de peso médio?"))

        assert result["context_sufficiency"] == "partial"


class TestGradeContextSufficientOrPartialGoesDirectToGenerate:
    """Desde o grupo 4, `grade_context` roteia o fluxo de verdade —
    `sufficient`/`partial` vão direto para `generate` sem reformular. O
    caso `insufficient` (reformula, depois desiste) é testado em
    `test_reformulation_flow.py`."""

    def test_sufficient_verdict_generates_directly(self, service):
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content="SUFFICIENT")
        mock_generation = _mock_generation()

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", mock_generation), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(_input_state("Qual o ganho de peso médio?"))

        assert result["context_sufficiency"] == "sufficient"
        assert result["reformulation_count"] == 0
        mock_generation.invoke.assert_called_once()

    def test_partial_verdict_generates_directly(self, service):
        mock_utility = MagicMock()
        mock_utility.invoke.return_value = MagicMock(content="PARTIAL")
        mock_generation = _mock_generation()

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", mock_generation), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[_mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(_input_state("Qual o ganho de peso médio?"))

        assert result["context_sufficiency"] == "partial"
        assert result["reformulation_count"] == 0
        mock_generation.invoke.assert_called_once()
        assert result["answer"] == "O ganho de peso médio foi registrado ao longo do experimento."


class TestGradeContextSkipsCallWhenContextAlreadyEmpty:
    def test_no_docs_retrieved_skips_llm_call(self, service):
        """Quando o piso de recusa por similaridade já zerou o contexto
        (`insufficient_context=True`), não há nada para julgar
        semanticamente — `generate` já vai recusar sem chamar nenhum LLM."""
        mock_utility = MagicMock()

        with patch.object(service, "llm_utility", mock_utility), \
             patch.object(service, "llm_generation", _mock_generation()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[]):
            result = service.graph.invoke(_input_state("Pergunta totalmente fora do escopo"))

        mock_utility.invoke.assert_not_called()
        assert result["context_sufficiency"] == "insufficient"
