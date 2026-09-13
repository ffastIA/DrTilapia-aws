# CAMINHO: backend/app/utils/chunking.py
"""Chunking contínuo ao longo do documento, com rastreamento de página.

`RecursiveCharacterTextSplitter.split_documents()` trata cada `Document` de
entrada como independente — se cada página do PDF vira um `Document`, o
split (e o overlap) nunca atravessa a quebra de página, e conteúdo dividido
entre duas páginas fica órfão. Esta função concatena as páginas num único
texto antes de dividir, preservando a atribuição de página de cada chunk
resultante via um mapa de offsets.
"""
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

_PAGE_SEPARATOR = "\n\n"


def split_pages_continuous(
    pages: List[Document],
    splitter: RecursiveCharacterTextSplitter,
) -> List[Document]:
    """Concatena páginas e divide o texto contínuo, mantendo a página de origem.

    `pages`: um `Document` por página (já limpo por `clean_loaded_pages`),
    cada um com `metadata['page']` (0-indexed) e `metadata['source']`.
    `splitter`: já construído pelo chamador com `add_start_index=True` —
    esta função não lê configuração nem constrói o splitter, para que
    `rag_service.py` continue controlando seu próprio `chunk_size`/
    `chunk_overlap` efetivo sem duplicar a lógica de split e atribuição
    de página.
    """
    if not pages:
        return []

    source = pages[0].metadata.get("source")

    parts: List[str] = []
    page_ranges: List[Tuple[int, int, int]] = []  # (start, end_exclusivo, page_num)
    offset = 0
    for i, page in enumerate(pages):
        text = page.page_content or ""
        start = offset
        parts.append(text)
        offset += len(text)
        page_ranges.append((start, offset, page.metadata.get("page", i)))
        if i < len(pages) - 1:
            parts.append(_PAGE_SEPARATOR)
            offset += len(_PAGE_SEPARATOR)
    full_text = "".join(parts)

    def page_for_offset(pos: int) -> int:
        pos = max(0, min(pos, len(full_text) - 1)) if full_text else 0
        for start, end, page_num in page_ranges:
            if start <= pos < end:
                return page_num
        # Offset caiu no separador entre páginas — atribui à página seguinte,
        # que é para onde esse trecho de fato está "entrando".
        for start, end, page_num in page_ranges:
            if pos < end:
                return page_num
        return page_ranges[-1][2] if page_ranges else 0

    chunks = splitter.create_documents(
        [full_text],
        metadatas=[{"source": source}] if source else None,
    )

    for chunk in chunks:
        start_index = chunk.metadata.get("start_index", 0)
        end_index = start_index + len(chunk.page_content)
        page_start = page_for_offset(start_index)
        page_end = page_for_offset(max(start_index, end_index - 1))
        chunk.metadata["page_start"] = page_start
        chunk.metadata["page_end"] = page_end
        # Sempre setado (não só quando page_start == page_end): código como
        # `_make_retrieval_dedup_key` lê `metadata['page']` diretamente, e
        # omiti-lo para chunks que atravessam página quebraria isso.
        chunk.metadata["page"] = page_start

    return chunks
