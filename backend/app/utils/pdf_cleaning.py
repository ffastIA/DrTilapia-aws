"""
PDF Cleaning Module for DrTilápia RAG
Ultra-conservative strategy: preserve ALL scientific data, remove ONLY obvious noise
Target: 100% data preservation, <10% editorial noise removal
"""

import re
import logging
from typing import Tuple, Dict, List

logger = logging.getLogger(__name__)


def is_page_number_line(line: str) -> bool:
    """
    Detects pure page numbers: 1/12, 2/12, 11/12, etc.
    These are obvious editorial noise.
    """
    if not line.strip():
        return False

    # Pattern: digits/digits (page numbers)
    if re.match(r'^\s*\d+/\d+\s*$', line.strip()):
        return True

    return False


def is_copyright_or_legal(line: str) -> bool:
    """
    Detects copyright, legal notices, and similar noise.
    VERY conservative - only removes obvious legal text.
    """
    if not line.strip():
        return False

    line_lower = line.lower().strip()

    # Only remove EXPLICIT copyright
    if re.match(r'^(©|copyright|all rights reserved)', line_lower):
        return True

    return False


def contains_scientific_value(line: str) -> bool:
    """
    Checks if line has scientific value and should be PRESERVED.
    AGGRESSIVELY preserves anything that might be data.
    """
    if not line.strip():
        return False

    line_stripped = line.strip()
    line_lower = line_stripped.lower()

    # PRESERVE: Any line with numbers + units
    if re.search(r'\d+\s*(mg|kg|g|μm|nm|mm|cm|m|°C|°F|K|%|ppm|pH|ml|l|h|min|sec|s|Hz|kHz|V|mV|A|mA|W|kW|um)',
                 line_stripped, re.IGNORECASE):
        return True

    # PRESERVE: Standard deviation notation (X.XX ± Y.YY or (X.XX))
    if re.search(r'\d+\.?\d*\s*±\s*\d+\.?\d*', line_stripped):
        return True

    # PRESERVE: Any line with parenthesized numbers (confidence intervals, SEM, etc)
    if re.search(r'\(\s*\d+\.?\d*\s*\)', line_stripped):
        return True

    # PRESERVE: p-values
    if re.search(r'p\s*[=<>]\s*0?\.\d+', line_stripped, re.IGNORECASE):
        return True

    # PRESERVE: Sample size notation
    if re.search(r'n\s*=\s*\d+', line_stripped, re.IGNORECASE):
        return True

    # PRESERVE: Ratio notation (1:10, 1/10, etc)
    if re.search(r'\d+[\:/]\d+', line_stripped):
        return True

    # PRESERVE: Scientific section headers
    scientific_sections = [
        'introduction', 'material', 'method', 'results', 'discussion',
        'conclusion', 'abstract', 'resumo', 'experimental', 'analysis',
        'table', 'tabela', 'figure', 'figura'
    ]
    if any(section in line_lower for section in scientific_sections):
        return True

    # PRESERVE: Treatment/Group/Control identifiers
    if re.search(r'(treatment|group|control|contrast|trial|experiment)', line_lower):
        return True

    # PRESERVE: Result indicators
    if re.search(r'(result|finding|observation|data|measurement|value|parameter)', line_lower):
        return True

    # PRESERVE: Any line with capital letters and numbers (likely table/data)
    if re.search(r'[A-Z].*\d', line_stripped):
        return True

    # PRESERVE: Lines starting with common table/figure identifiers
    if re.match(r'^(Table|Figure|Tabela|Figura|Fig|Tab)', line_stripped):
        return True

    # PRESERVE: Any all-uppercase word followed by content (likely column headers)
    if re.search(r'\b[A-Z]{2,}\b', line_stripped):
        return True

    # PRESERVE: Anything with percentage sign
    if '%' in line_stripped:
        return True

    # PRESERVE: Anything with mathematical operators
    if re.search(r'[=±×÷∑∫√∞≤≥≠<>]', line_stripped):
        return True

    return False


def remove_noise_lines(text: str) -> Tuple[str, Dict]:
    """
    ULTRA-CONSERVATIVE: Remove ONLY obvious page numbers and copyright.
    PRESERVE everything else that could be scientific data.

    Returns:
        (cleaned_text, stats_dict)
    """
    lines = text.split('\n')
    cleaned_lines = []

    stats = {
        'total_lines': len(lines),
        'lines_removed': 0,
        'lines_kept': 0,
        'removed_page_numbers': 0,
        'removed_copyright': 0,
        'examples_removed': [],
    }

    for line in lines:
        if not line.strip():
            # Remove empty lines to compact
            stats['lines_removed'] += 1
            continue

        if is_page_number_line(line):
            stats['lines_removed'] += 1
            stats['removed_page_numbers'] += 1
            continue

        if is_copyright_or_legal(line):
            stats['lines_removed'] += 1
            stats['removed_copyright'] += 1
            if len(stats['examples_removed']) < 3:
                stats['examples_removed'].append(f"Copyright: {line.strip()[:60]}")
            continue

        # PRESERVE everything else
        cleaned_lines.append(line)
        stats['lines_kept'] += 1

    cleaned_text = '\n'.join(cleaned_lines)
    return cleaned_text, stats


def log_cleaning_stats(stats: Dict) -> None:
    """Log cleaning statistics"""
    total = stats['total_lines']
    removed = stats['lines_removed']
    kept = stats['lines_kept']

    removal_pct = (removed / total * 100) if total > 0 else 0
    keep_pct = (kept / total * 100) if total > 0 else 0

    logger.info(
        f"\n{'=' * 60}\n"
        f"PDF CLEANING STATISTICS (ULTRA-CONSERVATIVE)\n"
        f"{'=' * 60}\n"
        f"Total lines: {total}\n"
        f"Lines kept: {kept} ({keep_pct:.1f}%)\n"
        f"Lines removed: {removed} ({removal_pct:.1f}%)\n"
        f"\nRemoval breakdown:\n"
        f"  - Page numbers: {stats['removed_page_numbers']}\n"
        f"  - Copyright: {stats['removed_copyright']}\n"
        f"\nStrategy: PRESERVE ALL scientific data, remove ONLY obvious noise\n"
        f"{'=' * 60}\n"
    )


def clean_pdf_text(text: str) -> str:
    """
    ULTRA-CONSERVATIVE cleaning: preserve 100% of scientific data.

    Only removes:
    - Page numbers (1/12, 2/12, etc)
    - Copyright/legal notices
    - Empty lines (for compaction)

    PRESERVES:
    - ALL numbers and units
    - ALL tables and figures
    - ALL scientific sections
    - ALL treatment/control identifiers
    - ALL results and data

    Args:
        text: Raw text extracted from PDF

    Returns:
        Cleaned text with 100% scientific data preserved
    """
    if not text or not text.strip():
        logger.warning("Empty or None text received in clean_pdf_text")
        return text

    # Process lines
    cleaned_text, stats = remove_noise_lines(text)

    # Log statistics
    log_cleaning_stats(stats)

    return cleaned_text


# Legacy function names for backward compatibility
def clean_loaded_pages(docs):
    """
    Legacy function for compatibility with existing code
    Cleans a list of LangChain Document objects
    """
    cleaned_docs = []
    for doc in docs:
        if hasattr(doc, 'page_content'):
            cleaned_content = clean_pdf_text(doc.page_content)
            # Create new document with cleaned content
            cleaned_doc = type(doc)(
                page_content=cleaned_content,
                metadata=doc.metadata if hasattr(doc, 'metadata') else {}
            )
            cleaned_docs.append(cleaned_doc)
        else:
            cleaned_docs.append(doc)
    return cleaned_docs


def is_editorial_or_low_value(text: str) -> bool:
    """
    Legacy function for compatibility with existing code
    ULTRA-CONSERVATIVE: Only return True for OBVIOUS garbage
    """
    if is_page_number_line(text) or is_copyright_or_legal(text):
        return True
    return False


def contains_scientific_signal(text: str) -> bool:
    """
    Legacy function for compatibility with existing code
    Check if text has scientific value
    """
    return contains_scientific_value(text)