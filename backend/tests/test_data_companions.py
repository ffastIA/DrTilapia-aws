# CAMINHO: backend/tests/test_data_companions.py
"""Testes para `_add_data_companion_chunks` limitado — teto total (não por
arquivo), elegibilidade restrita ao top-3 do ranking, orçamento de
caracteres respeitado."""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import get_rag_service
from app.utils.rag_config import DATA_COMPANION_MAX_TOTAL


@pytest.fixture
def service():
    return get_rag_service()


def _ranked_doc(similarity: float, file_id: str, db_id: str) -> Document:
    return Document(
        page_content="conteúdo do chunk recuperado",
        metadata={"similarity": similarity, "db_id": db_id, "original_file_id": file_id},
    )


def _table_row(row_id: str, digits: int, chars: int = 200) -> dict:
    content = ("1234567890" * ((digits // 10) + 1))[:digits] + ("a" * max(chars - digits, 0))
    return {"id": row_id, "content": content, "metadata": {}}


class TestDataCompanionCap:
    def test_total_cap_applies_across_multiple_eligible_files_not_per_file(self, service):
        """4 arquivos elegíveis, cada um com candidatos de sobra — o total
        de companions nunca deve passar de DATA_COMPANION_MAX_TOTAL, mesmo
        que isso signifique 0 companions de algum arquivo."""
        docs = [
            _ranked_doc(0.9, "file-a", "rank-a"),
            _ranked_doc(0.85, "file-b", "rank-b"),
            _ranked_doc(0.8, "file-c", "rank-c"),
        ]

        def fake_table(name):
            mock = MagicMock()

            def fake_execute():
                # Cada arquivo tem 5 candidatos ricos em dígitos — mais que
                # o suficiente para estourar o teto total sozinho.
                resp = MagicMock()
                resp.data = [_table_row(f"comp-{i}", digits=150) for i in range(5)]
                return resp

            mock.select.return_value.filter.return_value.execute = fake_execute
            return mock

        with patch.object(service.supabase_admin, "table", side_effect=fake_table):
            result = service._add_data_companion_chunks(docs)

        companions = [d for d in result if d.metadata.get("companion")]
        assert len(companions) <= DATA_COMPANION_MAX_TOTAL

    def test_file_outside_top_3_is_not_eligible(self, service):
        """Um arquivo cujo único chunk está no rank 4+ não pode injetar
        companions — só arquivos com chunk no top-3 do ranking são elegíveis."""
        docs = [
            _ranked_doc(0.9, "file-a", "rank-0"),
            _ranked_doc(0.85, "file-a", "rank-1"),
            _ranked_doc(0.8, "file-a", "rank-2"),
            _ranked_doc(0.5, "file-far", "rank-3"),  # fora do top-3
        ]

        calls = []

        def fake_table(name):
            mock = MagicMock()

            def fake_execute():
                calls.append(True)
                resp = MagicMock()
                resp.data = [_table_row("comp-0", digits=100)]
                return resp

            mock.select.return_value.filter.return_value.execute = fake_execute
            return mock

        with patch.object(service.supabase_admin, "table", side_effect=fake_table):
            service._add_data_companion_chunks(docs)

        # Só "file-a" (elegível) deveria gerar consulta — "file-far" não.
        assert len(calls) == 1

    def test_char_budget_is_respected(self, service):
        """Um candidato maior que o orçamento restante não deve ser
        adicionado, mesmo sendo o mais rico em dígitos."""
        from app.utils.rag_config import CONTEXT_CHAR_BUDGET

        # `docs` já consome quase todo o orçamento.
        huge_doc = Document(
            page_content="x" * (CONTEXT_CHAR_BUDGET - 50),
            metadata={"similarity": 0.9, "db_id": "rank-0", "original_file_id": "file-a"},
        )

        def fake_table(name):
            mock = MagicMock()

            def fake_execute():
                resp = MagicMock()
                # Candidato maior que o orçamento restante (50 chars).
                resp.data = [_table_row("comp-0", digits=100, chars=500)]
                return resp

            mock.select.return_value.filter.return_value.execute = fake_execute
            return mock

        with patch.object(service.supabase_admin, "table", side_effect=fake_table):
            result = service._add_data_companion_chunks([huge_doc])

        companions = [d for d in result if d.metadata.get("companion")]
        assert companions == []

    def test_disabled_flag_skips_companions_entirely(self, service, monkeypatch):
        docs = [_ranked_doc(0.9, "file-a", "rank-0")]
        with patch("app.services.rag_service.DATA_COMPANION_ENABLED", False), \
             patch.object(service.supabase_admin, "table") as mock_table:
            result = service._add_data_companion_chunks(docs)
        mock_table.assert_not_called()
        assert result == docs

    def test_no_eligible_file_ids_returns_docs_unchanged(self, service):
        doc_without_file_id = Document(page_content="x", metadata={"similarity": 0.9, "db_id": "rank-0"})
        result = service._add_data_companion_chunks([doc_without_file_id])
        assert result == [doc_without_file_id]

    def test_empty_docs_returns_empty(self, service):
        assert service._add_data_companion_chunks([]) == []
