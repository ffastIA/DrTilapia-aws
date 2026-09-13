"""Detecção de extração de PDF incompleta.

Complementa `_is_text_garbled` (que detecta texto ausente ou com encoding
quebrado) cobrindo um modo de falha diferente: extração que produz **estrutura
sem conteúdo** — cabeçalhos de seção, cabeçalhos de tabela sem linhas de dados,
e números órfãos que perderam seus rótulos.

Os limiares foram calibrados contra os 4 documentos reais do acervo (3 íntegros,
1 quebrado). Duas métricas foram testadas e **descartadas** por não discriminarem:
fração de tokens curtos (≤2 caracteres) e fração de tokens de 1 caractere — ambas
medem idioma, não qualidade, e davam valores *maiores* para um documento íntegro
em português do que para o quebrado.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Sequence

# Limiares calibrados. Medidos: documento quebrado 51 palavras/página e 0,082 de
# números isolados; íntegros 216-394 palavras e 0,005-0,023 de números isolados.
# Escolhidos com folga dos dois lados para pegar falha grosseira, não caso limítrofe.
MIN_WORDS_PER_PAGE = int(os.getenv("EXTRACTION_MIN_WORDS_PER_PAGE", "120"))
MAX_ISOLATED_NUMBER_RATIO = float(os.getenv("EXTRACTION_MAX_ISOLATED_NUMBER_RATIO", "0.05"))
MAX_SPARSE_PAGE_RATIO = float(os.getenv("EXTRACTION_MAX_SPARSE_PAGE_RATIO", "0.5"))

_ISOLATED_NUMBER = re.compile(r"^\d+([.,]\d+)?$")


@dataclass
class PageQuality:
    words: int
    isolated_number_ratio: float
    sparse: bool


@dataclass
class ExtractionQuality:
    """Resultado da avaliação, pronto para virar metadado auditável."""
    pages: int
    total_words: int
    mean_words_per_page: float
    mean_isolated_number_ratio: float
    sparse_pages: int
    sparse_page_ratio: float
    adequate: bool
    reason: str

    def as_metadata(self) -> dict:
        return asdict(self)


def _page_quality(text: str) -> PageQuality:
    tokens = [t for t in re.split(r"\s+", (text or "").strip()) if t]
    words = len(tokens)
    if words == 0:
        return PageQuality(words=0, isolated_number_ratio=0.0, sparse=True)

    isolated_numbers = sum(1 for t in tokens if _ISOLATED_NUMBER.match(t))
    ratio = isolated_numbers / words

    # Uma página é esparsa quando tem pouco texto OU quando o pouco que tem é
    # majoritariamente número solto — a assinatura de tabela sem linhas de dados.
    sparse = words < MIN_WORDS_PER_PAGE or ratio > MAX_ISOLATED_NUMBER_RATIO
    return PageQuality(words=words, isolated_number_ratio=ratio, sparse=sparse)


def assess_extraction(page_texts: Sequence[str]) -> ExtractionQuality:
    """Avalia a extração de um documento inteiro.

    O julgamento é do documento, não de páginas isoladas: uma capa ou uma página
    de referências legitimamente tem pouco texto, e reprovar por isso geraria
    falso positivo. O critério é a *fração* de páginas esparsas.
    """
    if not page_texts:
        return ExtractionQuality(
            pages=0, total_words=0, mean_words_per_page=0.0,
            mean_isolated_number_ratio=0.0, sparse_pages=0, sparse_page_ratio=1.0,
            adequate=False, reason="nenhuma página extraída",
        )

    qualities = [_page_quality(text) for text in page_texts]
    pages = len(qualities)
    total_words = sum(q.words for q in qualities)
    sparse_pages = sum(1 for q in qualities if q.sparse)
    sparse_ratio = sparse_pages / pages
    mean_words = total_words / pages
    mean_ratio = sum(q.isolated_number_ratio for q in qualities) / pages

    adequate = sparse_ratio <= MAX_SPARSE_PAGE_RATIO
    if adequate:
        reason = "extração adequada"
    else:
        reason = (
            f"{sparse_pages} de {pages} páginas esparsas "
            f"({sparse_ratio:.0%} > {MAX_SPARSE_PAGE_RATIO:.0%}); "
            f"média de {mean_words:.0f} palavras/página "
            f"(mínimo {MIN_WORDS_PER_PAGE}) e "
            f"{mean_ratio:.1%} de números isolados "
            f"(máximo {MAX_ISOLATED_NUMBER_RATIO:.1%})"
        )

    return ExtractionQuality(
        pages=pages,
        total_words=total_words,
        mean_words_per_page=round(mean_words, 1),
        mean_isolated_number_ratio=round(mean_ratio, 4),
        sparse_pages=sparse_pages,
        sparse_page_ratio=round(sparse_ratio, 3),
        adequate=adequate,
        reason=reason,
    )
