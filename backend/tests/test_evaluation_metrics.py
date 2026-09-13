# CAMINHO: backend/tests/test_evaluation_metrics.py
"""Testes para `evaluation/metrics.py` — normalização numérica e detecção de
recusa, os dois defeitos concretos que mascaravam a regressão de qualidade
do RAG por medir errado, não por o sistema estar errado.
"""
from evaluation.metrics import (
    is_refusal,
    looks_like_empty_skeleton,
    mention_coverage,
    normalize,
    passage_rank,
)


class TestDecimalNormalization:
    """Vírgula (pt-BR) e ponto (formato dos PDFs em inglês) decimais devem
    comparar como equivalentes — casos reais do golden set."""

    def test_comma_and_period_decimal_are_equivalent(self):
        assert normalize("64,10%") == normalize("64.10%")
        assert normalize("0,44") == normalize("0.44")
        assert normalize("21,02%") == normalize("21.02%")

    def test_thousand_separator_is_not_treated_as_decimal(self):
        """'17,000' (milhar no formato inglês) não pode virar '17.000'
        tratado como se fosse um decimal de 3 casas."""
        normalized = normalize("17,000")
        assert normalized == "17,000"

    def test_portuguese_thousand_separator_untouched(self):
        assert normalize("R$ 17.000") == "r$ 17.000"
        assert normalize("12.280.000") == "12.280.000"

    def test_superscript_digits_normalize_to_plain_digits(self):
        assert normalize("1,26 x 10⁸") == normalize("1.26 x 108")

    def test_mention_coverage_matches_across_decimal_formats(self):
        answer = "O tratamento PRO+MOS apresentou o maior RPL, com 64.10%."
        coverage = mention_coverage(answer, ["PRO+MOS com o maior RPL (64,10%)"])
        assert coverage == 1.0

    def test_mention_coverage_matches_fis_values_across_formats(self):
        answer = "A população SAW apresentou o maior FIS (0.44) entre todas as amostradas."
        coverage = mention_coverage(answer, ["SAW com FIS mais alto (0,44)"])
        assert coverage == 1.0

    def test_passage_rank_matches_across_decimal_formats(self):
        contents = ["O tratamento PRO+MOS obteve 64.10% de proteção relativa."]
        rank = passage_rank("PRO+MOS obteve 64,10% de proteção", contents)
        assert rank == 0


class TestIsRefusalNotCoupledToLength(object):
    """`is_refusal` não pode depender de corte de tamanho — o template de
    resposta pode produzir uma recusa substancialmente mais longa que 400
    chars, e uma resposta curta sem marcador de recusa não é recusa."""

    def test_long_answer_matching_refusal_message_is_a_refusal(self):
        from app.services.rag_service import get_rag_service
        service = get_rag_service()
        refusal_pt = service._build_refusal_message("pt-BR")
        padded = refusal_pt + " " * 350  # ultrapassa o corte antigo de 400 chars
        assert is_refusal(padded)

    def test_exact_refusal_message_pt_is_a_refusal(self):
        from app.services.rag_service import get_rag_service
        service = get_rag_service()
        assert is_refusal(service._build_refusal_message("pt-BR"))

    def test_exact_refusal_message_en_is_a_refusal(self):
        from app.services.rag_service import get_rag_service
        service = get_rag_service()
        assert is_refusal(service._build_refusal_message("en"))

    def test_short_substantive_answer_without_marker_is_not_a_refusal(self):
        assert not is_refusal("O KV é 1,2 para este lote.")

    def test_empty_answer_is_a_refusal(self):
        assert is_refusal("")


class TestLooksLikeEmptySkeleton:
    """Detecta resposta formalmente estruturada mas substantivamente vazia
    — o sintoma reportado ('Dados numéricos não disponíveis no contexto'
    citando os 4 documentos da base). Não depende de cabeçalho de seção,
    de propósito: o formato de resposta muda para prosa contínua na change
    seguinte deste programa."""

    def test_multi_section_skeleton_is_detected(self):
        answer = (
            "**Dados do Estudo:**\n"
            "Dados numéricos não disponíveis no contexto.\n\n"
            "**Interpretação:**\n"
            "O contexto não fornece informações específicas sobre o tema.\n\n"
            "**Implicações / Recomendações:**\n"
            "Não há conclusões explícitas no contexto sobre esse tema."
        )
        assert looks_like_empty_skeleton(answer)

    def test_short_single_deflection_is_detected(self):
        answer = "O contexto não fornece informações específicas sobre esse tema."
        assert looks_like_empty_skeleton(answer)

    def test_english_skeleton_is_detected(self):
        answer = "This document does not provide specific information about this topic."
        assert looks_like_empty_skeleton(answer)

    def test_real_substantive_answer_is_not_a_skeleton(self):
        answer = (
            "O tratamento PRO+MOS apresentou o maior nível de proteção relativa, "
            "com 64,10%, enquanto o tratamento MOS teve o menor, com 21,02%."
        )
        assert not looks_like_empty_skeleton(answer)

    def test_long_answer_with_one_incidental_gap_is_not_a_skeleton(self):
        """Uma resposta longa e substantiva não deve ser marcada como
        esqueleto só porque UMA seção entre várias não tinha dado — o padrão
        real é dominado por marcadores, não uma menção isolada."""
        answer = (
            "O KV é calculado dividindo a massa corporal pelo volume elipsoidal "
            "estimado a partir do comprimento total, altura e largura do peixe. "
            "Lotes com KV mais alto apresentaram, em média, maior rendimento de "
            "carcaça no abate, segundo o estudo de referência. " * 3
            + "O contexto não fornece informações específicas sobre variação sazonal."
        )
        assert not looks_like_empty_skeleton(answer)

    def test_empty_answer_is_not_a_skeleton(self):
        """Resposta vazia é coberta por `is_refusal`, não por isto."""
        assert not looks_like_empty_skeleton("")
