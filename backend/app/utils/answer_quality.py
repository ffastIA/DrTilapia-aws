# CAMINHO: backend/app/utils/answer_quality.py
"""Detecção de padrões de baixa qualidade em respostas geradas, e
verificação determinística de afirmações numéricas contra o contexto.

Vive em `app/utils/` (não em `evaluation/`) porque é usado pela produção
(`RAGService.evaluate`/`verify_numeric` no grafo LangGraph) — o harness de
avaliação reusa a mesma implementação em vez de manter uma cópia própria,
para produção e medição nunca divergirem silenciosamente sobre o que conta
como "resposta vazia" ou "número inventado".
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

_SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

# Vírgula decimal (pt-BR) vs ponto decimal (formato dos PDFs em inglês, e do
# que os modelos geram). Só casa 1-2 dígitos após a vírgula seguidos de
# fronteira de palavra — "64,10" vira "64.10", mas "17,000" (milhar) não é
# tocado, porque o 3º dígito imediatamente depois impede a fronteira de
# exigir `\b` logo após os 2 dígitos capturados.
_DECIMAL_COMMA_RE = re.compile(r"(\d),(\d{1,2})\b")


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação tolerante a ruído de extração de PDF
    e a formatações numéricas equivalentes (vírgula/ponto decimal, dígitos
    sobrescritos) — sem isso, uma resposta correta como "64.10%" pontua como
    ausente contra um golden set escrito "64,10%", e vice-versa (e um
    "1,26 x 10⁸" na resposta não bate contra um "1.26 x 108" no contexto).
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = text.translate(_SUPERSCRIPT_DIGITS)
    text = _DECIMAL_COMMA_RE.sub(r"\1.\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


_SKELETON_MARKERS = (
    "não disponível no contexto",
    "nao disponivel no contexto",
    "não disponíveis no contexto",
    "nao disponiveis no contexto",
    "não fornece informações",
    "nao fornece informacoes",
    "não fornece informação",
    "nao fornece informacao",
    "não há dados",
    "nao ha dados",
    "não há informações",
    "nao ha informacoes",
    "não consta no contexto",
    "nao consta no contexto",
    "não foi possível encontrar",
    "nao foi possivel encontrar",
    "not available in the context",
    "no data available in the context",
    "does not provide information",
    "does not provide specific information",
)

# Resposta dominada por um único marcador de "sem dados" costuma ser esse o
# conteúdo inteiro — acima disso, é provável que haja substância real em
# volta do marcador (ex.: uma seção vazia entre outras com conteúdo real).
_SKELETON_SHORT_ANSWER_CHARS = 300


def looks_like_empty_skeleton(answer: str) -> bool:
    """Detecta o padrão de resposta formalmente estruturada mas sem
    conteúdo real — o sintoma que motivou o programa de melhoria do RAG.

    Não depende de cabeçalho de seção (`**Dados do Estudo:**`, `DATA:` etc.)
    de propósito: o formato de resposta é prosa contínua, não seções
    obrigatórias (ver `restore-rag-answer-quality`). Conta ocorrências de
    marcadores de "sem dados/sem informação" em pt-BR e inglês — 2+
    ocorrências é o padrão de uma resposta que reafirma a ausência de dados
    mais de uma vez; 1 ocorrência já basta numa resposta curta, onde é
    provável que seja o conteúdo inteiro.
    """
    normalized = normalize_text(answer)
    if not normalized:
        return False  # resposta vazia é coberta por `is_refusal`, não por isto
    hits = sum(normalized.count(marker) for marker in _SKELETON_MARKERS)
    if hits >= 2:
        return True
    return hits >= 1 and len(normalized) < _SKELETON_SHORT_ANSWER_CHARS


# Inteiro ou decimal (vírgula já convertida a ponto por `normalize_text`),
# com "%" opcional colado. Não tenta reconhecer separador de milhar
# (`17.000`) separadamente de decimal — ver `find_unsupported_numbers`.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")


def extract_numbers(text: str) -> List[str]:
    """Extrai valores numéricos de um texto, já normalizados (decimal
    unificado, sobrescrito convertido em dígito) para comparação direta
    contra outro texto igualmente normalizado.

    Filtra números de baixo sinal (um único dígito solto, sem decimal nem
    `%`) — tipicamente contagem/numeração estrutural ("3 grupos", "a
    segunda fase"), não uma afirmação quantitativa que valha a pena
    verificar contra o contexto.
    """
    normalized = normalize_text(text)
    numbers = []
    for match in _NUMBER_RE.finditer(normalized):
        token = match.group(0)
        digits_only = re.sub(r"\D", "", token)
        has_decimal = "." in token
        has_percent = "%" in token
        if has_decimal or has_percent or len(digits_only) >= 2:
            numbers.append(token)
    return numbers


def find_unsupported_numbers(answer: str, context: str) -> List[str]:
    """Números presentes na resposta que não aparecem no contexto
    fornecido — sinal determinístico de possível alucinação, sem custo de
    LLM. Ordem preservada, duplicatas removidas.

    Falso positivo conhecido e aceito: um número genuinamente derivado por
    cálculo simples a partir de dois valores do contexto (ex.: uma
    diferença percentual) não aparece literalmente e seria sinalizado —
    ver design.md de `add-rag-self-correction-loop`. O custo de um falso
    positivo é uma regeneração extra, não um erro.
    """
    normalized_context = normalize_text(context)
    seen = set()
    unsupported = []
    for number in extract_numbers(answer):
        if number in seen:
            continue
        seen.add(number)
        if number not in normalized_context:
            unsupported.append(number)
    return unsupported
