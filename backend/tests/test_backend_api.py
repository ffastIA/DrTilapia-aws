# CAMINHO: backend/tests/test_backend_api.py

import io
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app


@pytest.fixture
def client():
    """Fixture para criar um cliente de teste do FastAPI."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Fixture automática para limpar overrides de dependências após cada teste."""
    yield
    app.dependency_overrides.clear()


def find_upload_route():
    """Helper para encontrar a rota de upload inspecionando app.routes."""
    for route in app.routes:
        if hasattr(route, 'methods') and 'POST' in route.methods and 'upload' in route.path:
            return route.path
    raise ValueError("Rota de upload não encontrada")


def override_admin_user():
    """Helper para sobrescrever get_current_admin_user com um usuário admin mockado."""
    async def mock_admin_user():
        return {"id": 1, "email": "admin@example.com", "role": "admin"}
    app.dependency_overrides[main_module.get_current_admin_user] = mock_admin_user


def error_tolerant_client():
    """Helper para criar um cliente que não levanta exceções do servidor."""
    return TestClient(app, raise_server_exceptions=False)


def build_vector_file_summary():
    """Builder para um resumo de arquivo vetorial."""
    return {
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "storage_bucket": "bucket",
        "storage_path": "path/to/file",
        "total_chunks": 10,
        "active_chunks": 10,
        "deleted_chunks": 0,
        "deleted_at": None,
        "last_ingested_at": "2023-01-01T00:00:00Z",
        "status": "active",
        "metadata": {}
    }


def build_vector_file_detail():
    """Builder para detalhes de arquivo vetorial."""
    return build_vector_file_summary()


def build_delete_file_response():
    """Builder para resposta de exclusão de arquivo."""
    return {
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "documents_deleted": 10,
        "ingestion_logs_deleted": 1,
        "storage_deleted": True,
        "storage_bucket": "bucket",
        "storage_path": "path/to/file",
        "status": "success",
        "message": "Arquivo excluído com sucesso"
    }


def build_cleanup_vector_base_response():
    """Builder para resposta de limpeza da base vetorial."""
    return {
        "total_files_processed": 5,
        "total_documents_deleted": 50,
        "total_ingestion_logs_deleted": 5,
        "total_storage_deleted": 5,
        "status": "success",
        "message": "Base vetorial limpa com sucesso"
    }


def build_reindex_file_response():
    """Builder para resposta de reindexação de arquivos."""
    return {
        "processed_files": 1,
        "failed_files": 0,
        "total_chunks_created": 10,
        "status": "success",
        "message": "Arquivos reindexados com sucesso"
    }


def build_vector_chunk():
    """Builder para um chunk vetorial."""
    return {
        "id": "chunk123",
        "content": "Conteúdo do chunk",
        "metadata": {},
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "storage_bucket": "bucket",
        "storage_path": "path/to/file",
        "deleted_at": None,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "page": 1,
        "chunk_index": 0
    }


def build_vector_chunks_response():
    """Builder para resposta de chunks vetoriais."""
    return {
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "total_chunks": 10,
        "active_chunks": 10,
        "deleted_chunks": 0,
        "chunks": [build_vector_chunk()],
        "status": "success",
        "message": "Chunks recuperados com sucesso"
    }


def build_recover_file_content_response():
    """Builder para resposta de recuperação de conteúdo de arquivo."""
    return {
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "storage_bucket": "bucket",
        "storage_path": "path/to/file",
        "total_chunks": 10,
        "active_chunks": 10,
        "deleted_chunks": 0,
        "content": "Conteúdo recuperado",
        "chunks": [build_vector_chunk()],
        "status": "success",
        "message": "Conteúdo recuperado com sucesso"
    }


def build_recovery_diagnosis_response():
    """Builder para resposta de diagnóstico de recuperação."""
    return {
        "original_file_id": "file123",
        "original_file_name": "teste.pdf",
        "total_chunks": 10,
        "active_chunks": 10,
        "deleted_chunks": 0,
        "has_table_data": True,
        "has_storage": True,
        "recoverable_from_table": True,
        "recoverable_from_storage": True,
        "recoverable_from_both": True,
        "recoverable_from_none": False,
        "status": "success",
        "message": "Diagnóstico realizado com sucesso"
    }


def test_health_endpoint(client):
    """Testa o endpoint de saúde."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["ok", "online"]


def test_login_success(client, monkeypatch):
    """Testa login bem-sucedido."""
    async def mock_login(email, password):
        return {"access_token": "token123", "token_type": "bearer", "user": {"id": 1, "email": email}}
    monkeypatch.setattr(main_module.auth_service, "login", mock_login)
    payload = {"email": "admin@example.com", "password": "pass"}
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert "user" in data


def test_login_invalid_credentials(client, monkeypatch):
    """Testa login com credenciais inválidas."""
    async def mock_login(email, password):
        return None
    monkeypatch.setattr(main_module.auth_service, "login", mock_login)
    payload = {"email": "admin@example.com", "password": "wrong"}
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_chat_success(client, monkeypatch):
    """Testa chat bem-sucedido, incluindo as fontes reais na resposta."""
    from app.services.rag_service import AnswerResult

    def mock_get_answer(message, history):
        return AnswerResult(
            answer="Resposta mockada",
            sources=[{"file": "doc.pdf", "page_start": 0, "page_end": 1}],
        )
    monkeypatch.setattr(main_module.rag_service, "get_answer", mock_get_answer)
    payload = {"message": "Olá", "history": []}
    response = client.post("/consultoria/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Resposta mockada"
    assert data["sources"] == [{"file": "doc.pdf", "page_start": 0, "page_end": 1}]


def test_chat_internal_error(monkeypatch):
    """Testa erro interno no chat."""
    client = error_tolerant_client()
    async def mock_get_answer(message, history):
        raise Exception("Erro interno")
    monkeypatch.setattr(main_module.rag_service, "get_answer", mock_get_answer)
    payload = {"message": "Olá", "history": []}
    response = client.post("/consultoria/chat", json=payload)
    assert response.status_code == 500


def test_upload_pdf_success(client, monkeypatch):
    """Testa upload de PDF bem-sucedido."""
    upload_route = find_upload_route()
    async def mock_ingest_pdf(file_path, filename, *args, **kwargs):
        return {"status": "success"}
    monkeypatch.setattr(main_module.rag_service, "ingest_pdf", mock_ingest_pdf)
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000200 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n284\n%%EOF"
    files = {"file": ("teste.pdf", io.BytesIO(pdf_content), "application/pdf")}
    response = client.post(upload_route, files=files)
    assert response.status_code == 200


def test_upload_rejects_non_pdf(client):
    """Testa rejeição de upload de arquivo não PDF."""
    upload_route = find_upload_route()
    files = {"file": ("teste.txt", io.BytesIO(b"conteudo texto"), "text/plain")}
    response = client.post(upload_route, files=files)
    assert response.status_code in [400, 422]


def test_list_vector_files_success(client, monkeypatch):
    """Testa listagem de arquivos vetoriais bem-sucedida."""
    override_admin_user()
    def mock_list_files():
        return [build_vector_file_summary()]
    monkeypatch.setattr(main_module.vector_admin_service, "list_files", mock_list_files)
    response = client.get("/admin/vector-base/files")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_vector_file_success(client, monkeypatch):
    """Testa obtenção de detalhes de arquivo vetorial bem-sucedida."""
    override_admin_user()
    def mock_get_file(original_file_id):
        return build_vector_file_detail()
    monkeypatch.setattr(main_module.vector_admin_service, "get_file", mock_get_file)
    response = client.get("/admin/vector-base/files/file123")
    assert response.status_code == 200
    data = response.json()
    assert data["original_file_id"] == "file123"


def test_delete_vector_file_success(client, monkeypatch):
    """Testa exclusão de arquivo vetorial bem-sucedida."""
    override_admin_user()
    def mock_delete_file(original_file_id, confirmation_phrase, reason=None, hard_delete=True):
        return build_delete_file_response()
    monkeypatch.setattr(main_module.vector_admin_service, "delete_file", mock_delete_file)
    payload = {
        "confirmation_phrase": "CONFIRMAR_EXCLUSAO",
        "reason": "teste automatizado",
        "hard_delete": True
    }
    response = client.post("/admin/vector-base/files/file123/delete", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_cleanup_vector_base_success(client, monkeypatch):
    """Testa limpeza da base vetorial bem-sucedida.

    CUIDADO: o endpoint `/admin/vector-base/cleanup` chama
    `vector_admin_service.cleanup(...)`, não `cleanup_vector_base(...)` —
    mockar o nome errado (como esta função fazia antes) NÃO gera erro,
    porque `cleanup_vector_base` também existe como método real (chama
    `cleanup` internamente) — só não é o método que o endpoint de fato usa.
    O resultado: o mock nunca interceptava a chamada real, e este teste
    disparava uma limpeza VERDADEIRA contra o Supabase de produção toda vez
    que a suíte completa rodava. Foi assim que a base vetorial do RAG foi
    esvaziada repetidamente durante o desenvolvimento de
    `add-hybrid-lexical-vector-search` — descoberto inspecionando os logs
    de API do Supabase (padrão de GET+DELETE em lote repetido a cada
    execução de `pytest tests/`). Mockar sempre `cleanup`, o método que
    `app/main.py` realmente chama.
    """
    override_admin_user()
    def mock_cleanup(confirmation_phrase):
        return build_cleanup_vector_base_response()
    monkeypatch.setattr(main_module.vector_admin_service, "cleanup", mock_cleanup)
    payload = {"confirmation_phrase": "CONFIRMAR_LIMPEZA_TOTAL"}
    response = client.post("/admin/vector-base/cleanup", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_reindex_vector_files_success(client, monkeypatch):
    """Testa reindexação de arquivos vetoriais bem-sucedida."""
    override_admin_user()
    async def mock_reindex_files(confirmation_phrase, original_file_ids=None):
        return build_reindex_file_response()
    monkeypatch.setattr(main_module.vector_admin_service, "reindex_files", mock_reindex_files)
    payload = {
        "confirmation_phrase": "CONFIRMAR_REINDEXACAO",
        "original_file_ids": ["file1"]
    }
    response = client.post("/admin/vector-base/reindex", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_get_vector_file_chunks_success(client, monkeypatch):
    """Testa obtenção de chunks de arquivo vetorial bem-sucedida."""
    override_admin_user()
    def mock_get_file_chunks(original_file_id):
        return build_vector_chunks_response()
    monkeypatch.setattr(main_module.vector_admin_service, "get_file_chunks", mock_get_file_chunks)
    response = client.get("/admin/vector-base/files/file123/chunks")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_recover_vector_file_content_success(client, monkeypatch):
    """Testa recuperação de conteúdo de arquivo vetorial bem-sucedida."""
    override_admin_user()
    def mock_recover_file_content(original_file_id):
        return build_recover_file_content_response()
    monkeypatch.setattr(main_module.vector_admin_service, "recover_file_content", mock_recover_file_content)
    response = client.get("/admin/vector-base/files/file123/content")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_diagnose_vector_file_recovery_success(client, monkeypatch):
    """Testa diagnóstico de recuperação de arquivo vetorial bem-sucedido."""
    override_admin_user()
    def mock_diagnose_file_recovery(original_file_id):
        return build_recovery_diagnosis_response()
    monkeypatch.setattr(main_module.vector_admin_service, "diagnose_file_recovery", mock_diagnose_file_recovery)
    response = client.get("/admin/vector-base/files/file123/diagnosis")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"