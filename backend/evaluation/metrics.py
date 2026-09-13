"""Normalização e casamento de trechos para as métricas de recuperação.

Separado do executor porque é a parte com regra de negócio sutil: os chunks têm
fronteiras arbitrárias e o texto vem de extração de PDF, então comparar por
igualdade exata produziria falsos negativos sistemáticos.
"""
from __future__ import annotations

import re
from typing import Sequence

# Reexportados para os consumidores deste módulo (`run_eval.py`, testes) —
# implementação canônica em `app/utils/answer_quality.py`, usada também pela
# produção (`RAGService.evaluate`/`verify_numeric`), para produção e medição
# nunca divergirem silenciosamente sobre o que conta como "resposta vazia"
# ou sobre normalização de decimais/sobrescritos.
from app.utils.answer_quality import (  # noqa: F401
    looks_like_empty_skeleton,
    normalize_text as normalize,
)


def passage_rank(passage: str, retrieved_contents: Sequence[str]) -> int | None:
    """Posição (0-based) do primeiro chunk recuperado que contém o trecho.

    Retorna None se nenhum chunk o contém.
    """
    needle = normalize(passage)
    if not needle:
        return None
    for position, content in enumerate(retrieved_contents):
        if needle in normalize(content):
            return position
    return None


def is_refusal(answer: str) -> bool:
    """Detecta recusa por casamento contra as mensagens de recusa reais do
    sistema (`RAGService._build_refusal_message`), não por corte de tamanho.

    A versão anterior classificava por `len < 400 and marcador` ou `len <
    120` — acoplada ao formato da resposta. Um template de resposta mais
    longo (mesmo sendo substancialmente uma recusa) escapava do primeiro
    corte, e uma resposta curta e substantiva sem nenhum marcador de recusa
    caía no segundo corte só por ser curta. Casar contra a mensagem real
    elimina os dois falsos negativos/positivos ao preço de precisar chamar
    `get_rag_service()` — import local para não pesar o import deste módulo
    quando só a normalização/cobertura de menção são necessárias.
    """
    normalized = normalize(answer)
    if not normalized:
        return True

    from app.services.rag_service import get_rag_service

    service = get_rag_service()
    refusal_pt = normalize(service._build_refusal_message("pt-BR"))
    refusal_en = normalize(service._build_refusal_message("en"))
    return refusal_pt in normalized or refusal_en in normalized


def mention_coverage(answer: str, must_mention: Sequence[str]) -> float:
    """Fração dos pontos obrigatórios cujos termos numéricos/chave aparecem.

    Compara pelos tokens significativos de cada ponto (números e palavras longas),
    não pela frase inteira — a redação da resposta varia legitimamente.
    """
    if not must_mention:
        return 1.0

    normalized_answer = normalize(answer)
    covered = 0
    for point in must_mention:
        tokens = _significant_tokens(point)
        if not tokens:
            continue
        hits = sum(1 for token in tokens if token in normalized_answer)
        if hits / len(tokens) >= 0.6:
            covered += 1
    return covered / len(must_mention)


def _significant_tokens(text: str) -> list[str]:
    normalized = normalize(text)
    raw = re.findall(r"[a-záàâãéêíóôõúç0-9][a-záàâãéêíóôõúç0-9,.%-]*", normalized)
    return [token for token in raw if any(ch.isdigit() for ch in token) or len(token) > 4]
