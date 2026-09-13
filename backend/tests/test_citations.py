# CAMINHO: backend/tests/test_citations.py
"""Testes para `_build_sources`/`_extract_source_doc_info` — citações
discretas por página, não mais um span min/max sobre tudo que foi
recuperado, e companions que não introduzem arquivo novo sozinhos."""
import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service
from app.utils.rag_config import CITATION_MAX_FILES


@pytest.fixture
def service():
    return get_rag_service()


def _source_doc(file_name, page_start, page_end=None, companion=False):
    return {
        "original_file_name": file_name,
        "page_start": page_start,
        "page_end": page_end if page_end is not None else page_start,
        "companion": companion,
    }


class TestBuildSources:
    def test_two_chunks_from_one_file_list_exact_pages_not_full_span(self, service):
        """O bug relatado: 2 chunks específicos de um arquivo não podem
        virar uma citação cobrindo o documento inteiro."""
        source_docs = [_source_doc("BIP 2024 publicado.pdf", 3), _source_doc("BIP 2024 publicado.pdf", 9)]
        sources = service._build_sources(source_docs)
        assert len(sources) == 1
        assert sources[0]["file"] == "BIP 2024 publicado.pdf"
        assert sources[0]["pages"] == [3, 9]  # não [3, 4, 5, 6, 7, 8, 9]

    def test_chunk_spanning_pages_includes_all_pages_in_range(self, service):
        source_docs = [_source_doc("doc.pdf", 2, 4)]
        sources = service._build_sources(source_docs)
        assert sources[0]["pages"] == [2, 3, 4]

    def test_companion_only_file_is_excluded(self, service):
        """Um arquivo citado só por companion (densidade de dígitos, não
        ranking semântico) não deve aparecer nas fontes."""
        source_docs = [
            _source_doc("real-match.pdf", 1, companion=False),
            _source_doc("companion-only.pdf", 5, companion=True),
        ]
        sources = service._build_sources(source_docs)
        files = [s["file"] for s in sources]
        assert "real-match.pdf" in files
        assert "companion-only.pdf" not in files

    def test_companion_chunk_for_already_cited_file_is_included(self, service):
        """Um companion do MESMO arquivo já citado por um chunk genuíno
        deve contribuir com suas páginas."""
        source_docs = [
            _source_doc("doc.pdf", 1, companion=False),
            _source_doc("doc.pdf", 8, companion=True),
        ]
        sources = service._build_sources(source_docs)
        assert len(sources) == 1
        assert sources[0]["pages"] == [1, 8]

    def test_no_file_name_is_skipped(self, service):
        source_docs = [{"original_file_name": None, "page_start": 1, "page_end": 1, "companion": False}]
        assert service._build_sources(source_docs) == []

    def test_empty_source_docs_returns_empty(self, service):
        assert service._build_sources([]) == []

    def test_more_than_max_files_is_truncated_ordered_by_first_appearance(self, service):
        source_docs = [
            _source_doc(f"file-{i}.pdf", i) for i in range(CITATION_MAX_FILES + 3)
        ]
        sources = service._build_sources(source_docs)
        assert len(sources) == CITATION_MAX_FILES
        assert [s["file"] for s in sources] == [f"file-{i}.pdf" for i in range(CITATION_MAX_FILES)]

    def test_no_sources_when_only_companions_across_all_files(self, service):
        source_docs = [_source_doc("a.pdf", 1, companion=True), _source_doc("b.pdf", 2, companion=True)]
        assert service._build_sources(source_docs) == []


class TestExtractSourceDocInfo:
    def test_marks_companion_chunks(self, service):
        genuine = Document(page_content="x", metadata={"original_file_name": "a.pdf", "page": 1})
        companion = Document(
            page_content="y",
            metadata={"original_file_name": "a.pdf", "page": 2, "companion": True},
        )
        result = service._extract_source_doc_info([genuine, companion])
        assert result[0]["companion"] is False
        assert result[1]["companion"] is True

    def test_uses_page_start_end_when_present_falls_back_to_page(self, service):
        with_range = Document(
            page_content="x",
            metadata={"original_file_name": "a.pdf", "page_start": 2, "page_end": 4, "page": 2},
        )
        without_range = Document(
            page_content="y", metadata={"original_file_name": "a.pdf", "page": 7},
        )
        result = service._extract_source_doc_info([with_range, without_range])
        assert result[0]["page_start"] == 2 and result[0]["page_end"] == 4
        assert result[1]["page_start"] == 7 and result[1]["page_end"] == 7
