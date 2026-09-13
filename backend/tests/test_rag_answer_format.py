# CAMINHO: backend/tests/test_rag_answer_format.py
"""Testes de regressão de formato para restore-rag-answer-quality.

O sintoma que motivou esta change inteira: um prompt com cabeçalhos de
seção obrigatórios ("MANDATORY RESPONSE STRUCTURE") produzia respostas
formalmente estruturadas mas vazias para perguntas fora do escopo, e não
permitia recusa honesta. Estes testes travam a regressão em dois níveis:
o próprio prompt nunca mais deve conter os marcadores antigos, e o nó
`generate` deve converter o sentinela de recusa corretamente.
"""
import re
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service

# Marcadores do formato antigo (4 templates com cabeçalhos obrigatórios) —
# nenhum deve aparecer no prompt nem em uma resposta gerada.
_OLD_FORMAT_MARKERS = (
    "MANDATORY RESPONSE STRUCTURE",
    "**Dados do Estudo:**",
    "**Interpretação:**",
    "**Implicações",
    "DATA:",
    "METHODOLOGY:",
    "INTERPRETATION:",
    "LIMITATIONS:",
    "Empty section.",
    "COMPARISON:",
    "KEY DIFFERENCES:",
    "CONCLUSION:",
    "EXPERIMENTAL DESIGN:",
    "PROCEDURES:",
    "MEASUREMENTS:",
    "STATISTICAL ANALYSIS:",
)


@pytest.fixture
def service():
    return get_rag_service()


def _mock_utility_sufficient():
    """`grade_context` (add-rag-self-correction-loop) roda em todo
    `get_answer`, entre `retrieve` e `generate`, chamando `llm_utility`
    diretamente — independente de `_retrieve_docs_via_rpc` estar mockado.
    Sem isto, estes testes fariam uma chamada real à API a cada execução."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="SUFFICIENT")
    return mock


class TestSystemPromptIsProse:
    """`_build_system_prompt`: base única em prosa, sem cabeçalhos
    obrigatórios, para nenhum tipo de pergunta."""

    @pytest.mark.parametrize(
        "question_type", ["conceptual", "quantitative", "comparative", "methodological"]
    )
    def test_prompt_contains_no_old_format_markers(self, service, question_type):
        prompt = service._build_system_prompt(question_type, "Respond in English.")
        for marker in _OLD_FORMAT_MARKERS:
            assert marker not in prompt, f"marcador antigo '{marker}' vazou para o prompt de {question_type}"

    def test_prompt_instructs_continuous_prose(self, service):
        prompt = service._build_system_prompt("conceptual", "Respond in English.")
        assert "continuous prose" in prompt.lower()

    def test_prompt_contains_sentinel_instruction(self, service):
        for question_type in ["conceptual", "quantitative", "comparative", "methodological"]:
            prompt = service._build_system_prompt(question_type, "Respond in English.")
            assert service.NO_ANSWER_SENTINEL in prompt

    def test_prompt_no_longer_contains_poisoned_study_specific_examples(self, service):
        """Os exemplos com valores reais de um estudo específico (FIS
        0.44/0.05, DEST 0.00-0.818) eram um few-shot anchor perigoso —
        convite a vazar números de um estudo para perguntas sobre outro."""
        prompt = service._build_system_prompt("conceptual", "Respond in English.")
        assert "0.44" not in prompt
        assert "DEST" not in prompt
        assert "SAW" not in prompt

    def test_different_question_types_produce_different_emphasis(self, service):
        prompts = {
            qt: service._build_system_prompt(qt, "Respond in English.")
            for qt in ["conceptual", "quantitative", "comparative", "methodological"]
        }
        # Todos compartilham a mesma base — mas a linha de ênfase difere.
        assert len(set(prompts.values())) == 4


class TestGenerateSentinelHandling:
    """`generate` (via `get_answer`): sentinela textual de recusa é
    detectado e substituído pela mensagem de recusa real, sem citações."""

    def _mock_doc(self):
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

    def test_sentinel_response_becomes_refusal_with_no_sources(self, service):
        mock_response = MagicMock()
        mock_response.content = service.NO_ANSWER_SENTINEL
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual o efeito da dieta na tilápia do Nilo?", [])

        assert result.answer in (
            service._build_refusal_message("pt-BR"),
            service._build_refusal_message("en"),
        )
        assert result.sources == []

    def test_sentinel_with_surrounding_whitespace_is_still_detected(self, service):
        """O modelo pode envolver a resposta em espaço/quebra de linha —
        `generate` compara com `.strip()`."""
        mock_response = MagicMock()
        mock_response.content = f"  {service.NO_ANSWER_SENTINEL}  \n"
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual o efeito da dieta na tilápia do Nilo?", [])

        assert result.sources == []
        assert result.answer in (
            service._build_refusal_message("pt-BR"),
            service._build_refusal_message("en"),
        )

    def test_sentinel_embedded_after_prose_explanation_is_still_detected(self, service):
        """Regressão observada ao vivo (`oos-dieta-restritiva`, run
        `20260802T035819Z-pos-fase-a`): apesar da instrução pedir
        'exatamente X e nada mais', o modelo às vezes escreve uma explicação
        completa primeiro e só então acrescenta o sentinela no final. Um
        casamento por igualdade exata deixava isso passar como resposta
        válida — com fontes citadas que não sustentavam nada, o mesmo
        sintoma que esta change existe para eliminar."""
        mock_response = MagicMock()
        mock_response.content = (
            "Os documentos disponíveis não abordam diretamente o comportamento da "
            "tilápia do Nilo sob uma dieta restritiva. Portanto, não há informações "
            "específicas sobre o tema. `SEM_RESPOSTA_NO_CONTEXTO`"
        )
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual o efeito da dieta na tilápia do Nilo?", [])

        assert result.sources == []
        assert result.answer in (
            service._build_refusal_message("pt-BR"),
            service._build_refusal_message("en"),
        )

    def test_normal_answer_is_not_treated_as_sentinel(self, service):
        mock_response = MagicMock()
        mock_response.content = "O estudo encontrou ganho de peso médio de 45.2g no grupo tratado."
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual o ganho de peso médio?", [])

        assert result.answer == mock_response.content


class TestEvaluateIsTerminal:
    """`evaluate`: qualidade sem cabeçalho de seção. Desde
    `add-rag-self-correction-loop` (grupo 4), `evaluate` não dispara mais
    retry algum — o antigo laço pós-geração (`should_retry`/`retrieve_retry`,
    acionado por LOW_QUALITY) foi substituído pela reformulação
    pré-geração de `grade_context` (ver `test_grade_context.py` e
    `test_reformulation_flow.py`). Uma resposta LOW_QUALITY ainda é
    detectada e logada, mas o grafo termina ali — nunca gera de novo."""

    def _mock_doc(self):
        # Inclui os números citados pelas respostas mock desta classe — sem
        # isso, `verify_numeric` os marcaria como não suportados pelo
        # contexto e disparia uma chamada extra de regeneração, inflando
        # `call_count` e testando um comportamento diferente do que estes
        # testes verificam (evaluate/retry, não verify_numeric).
        return Document(
            page_content=(
                "Conteúdo científico de teste sobre tilápia, ganho de peso médio "
                "de 45.2g no grupo PRO+MOS, proteção relativa de 64,10% (PRO+MOS) "
                "e 21,02% (MOS). " * 20
            ),
            metadata={
                "similarity": 0.9,
                "db_id": "id-1",
                "original_file_name": "doc.pdf",
                "original_file_id": "file-1",
                "page": 1,
            },
        )

    def test_skeleton_answer_does_not_retry(self, service):
        """Uma resposta esqueleto é marcada LOW_QUALITY, mas o grafo não
        gera de novo por causa disso — só 1 chamada de geração."""
        skeleton_response = MagicMock()
        skeleton_response.content = (
            "O contexto não fornece informações específicas sobre o tema. "
            "Não há dados disponíveis no contexto."
        )
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = skeleton_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.graph.invoke(
                {
                    "question": "Qual o ganho de peso médio?", "context": "", "answer": "",
                    "evaluation": "", "language": "pt-BR", "history": [],
                    "question_type": "conceptual", "insufficient_context": False,
                    "source_docs": [], "context_confidence": "strong",
                    "effective_type": "conceptual", "unsupported_numbers": [],
                    "numeric_regen_count": 0, "context_sufficiency": "",
                    "retrieval_query": "", "reformulation_count": 0,
                }
            )

        assert mock_llm_generation.invoke.call_count == 1
        assert result["evaluation"] == "LOW_QUALITY"

    def test_substantive_answer_does_not_retry(self, service):
        good_response = MagicMock()
        good_response.content = "O estudo encontrou ganho de peso médio de 45.2g no grupo tratado com PRO+MOS."
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = good_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            service.get_answer("Qual o ganho de peso médio?", [])

        assert mock_llm_generation.invoke.call_count == 1

    def test_prose_answer_with_no_headers_is_high_quality(self, service):
        """Uma resposta em prosa (sem nenhum cabeçalho de seção) precisa
        passar pela avaliação — o `evaluate` novo não procura cabeçalho."""
        good_response = MagicMock()
        good_response.content = (
            "O tratamento PRO+MOS apresentou o maior nível de proteção relativa, "
            "com 64,10%, enquanto o tratamento MOS teve o menor, com 21,02%."
        )
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = good_response

        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(service, "_retrieve_docs_via_rpc", return_value=[self._mock_doc()]), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            result = service.get_answer("Qual tratamento teve o maior RPL?", [])

        assert result.answer == good_response.content
        assert mock_llm_generation.invoke.call_count == 1


class TestConfidenceCaveat:
    """`context_confidence` (strong/partial) instrui uma ressalva explícita
    no prompt de geração quando a similaridade não atinge o limiar de
    confiança alta — postura escolhida: responder com ressalva na zona de
    incerteza, não recusar."""

    def _mock_doc(self, similarity: float):
        return Document(
            page_content="Conteúdo científico de teste sobre tilápia. " * 20,
            metadata={
                "similarity": similarity,
                "db_id": "id-1",
                "original_file_name": "doc.pdf",
                "original_file_id": "file-1",
                "page": 1,
            },
        )

    def test_partial_confidence_adds_caveat_instruction_to_prompt(self, service):
        weak_score = (service.similarity_threshold + 0.53) / 2  # entre o piso e o limiar
        mock_response = MagicMock()
        mock_response.content = "Resposta com ressalva."
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        trace = {"top_similarity_raw": weak_score, "selection_reason": "relative_window"}
        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(
                 service, "_retrieve_docs_via_rpc",
                 side_effect=lambda *a, **kw: (
                     kw["trace_out"].update(trace) if kw.get("trace_out") is not None else None,
                     [self._mock_doc(weak_score)],
                 )[1],
             ), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            service.get_answer("Qual o ganho de peso médio?", [])

        system_prompt = mock_llm_generation.invoke.call_args[0][0][0].content
        assert "uncertainty" in system_prompt.lower() or "partial/moderate relevance" in system_prompt.lower()

    def test_strong_confidence_has_no_caveat_instruction(self, service):
        strong_score = service.similarity_threshold + 0.1
        mock_response = MagicMock()
        mock_response.content = "Resposta confiante."
        mock_llm_generation = MagicMock()
        mock_llm_generation.invoke.return_value = mock_response

        trace = {"top_similarity_raw": strong_score, "selection_reason": "relative_window"}
        with patch.object(service, "llm_generation", mock_llm_generation), \
             patch.object(service, "llm_utility", _mock_utility_sufficient()), \
             patch.object(
                 service, "_retrieve_docs_via_rpc",
                 side_effect=lambda *a, **kw: (
                     kw["trace_out"].update(trace) if kw.get("trace_out") is not None else None,
                     [self._mock_doc(strong_score)],
                 )[1],
             ), \
             patch.object(service, "_add_data_companion_chunks", side_effect=lambda docs: docs):
            service.get_answer("Qual o ganho de peso médio?", [])

        system_prompt = mock_llm_generation.invoke.call_args[0][0][0].content
        assert "partial/moderate relevance" not in system_prompt.lower()
