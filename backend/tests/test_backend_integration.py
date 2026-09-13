# CAMINHO: backend/tests/test_backend_integration.py

"""
Suíte de testes de integração real para o backend DrTilápia.

Este arquivo contém testes que interagem com o backend FastAPI em execução externa
via HTTP real, utilizando httpx. Não utiliza mocks nem TestClient.

Fixtures são configuradas com escopos coerentes para evitar ScopeMismatch.
"""

import os
import io
import time
import uuid
from typing import Dict, Any
from pathlib import Path
import pytest
import httpx


# Helpers

def build_admin_headers(token: str) -> Dict[str, str]:
    """
    Constrói os cabeçalhos para autenticação admin com Bearer token.
    """
    return {"Authorization": f"Bearer {token}"}


def login_real(client: httpx.Client, base_url: str, email: str, password: str) -> Dict[str, Any]:
    """
    Realiza login real via HTTP e retorna a resposta JSON.
    """
    response = client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()


def discover_upload_route(client: httpx.Client, base_url: str, headers: Dict[str, str]) -> str:
    """
    Descobre a rota de upload tentando POST controlado nas candidatas.
    Retorna a primeira rota que existe (não 404).
    """
    candidates = ["/consultoria/upload", "/admin/upload"]
    for route in candidates:
        try:
            response = client.post(f"{base_url}{route}", headers=headers, files={"file": ("test.pdf", b"dummy", "application/pdf")})
            if response.status_code != 404:
                return route
        except httpx.RequestError:
            continue
    raise ValueError("Nenhuma rota de upload encontrada")


def generate_minimal_pdf_bytes() -> bytes:
    """
    Gera bytes de um PDF mínimo contendo apenas texto ASCII.
    """
    # PDF simples com texto ASCII apenas
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000200 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
284
%%EOF"""
    return pdf_content


def load_test_pdf_bytes() -> bytes:
    """
    Carrega bytes do PDF de teste: usa DRT_TEST_PDF_PATH se existir, senão gera mínimo.
    """
    pdf_path = os.getenv("DRT_TEST_PDF_PATH")
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            return f.read()
    return generate_minimal_pdf_bytes()


def find_uploaded_file_record(client: httpx.Client, base_url: str, headers: Dict[str, str], filename: str) -> Dict[str, Any]:
    """
    Localiza o registro do arquivo enviado na listagem de arquivos.
    Compara por original_file_name ou filename.
    """
    response = client.get(f"{base_url}/admin/vector-base/files", headers=headers)
    response.raise_for_status()
    files = response.json()
    for file_record in files:
        if file_record.get("original_file_name") == filename or file_record.get("filename") == filename:
            return file_record
    raise ValueError(f"Arquivo '{filename}' não encontrado na listagem")


# Fixtures

@pytest.fixture(scope="session")
def base_url():
    """
    URL base do backend, lida de DRT_BASE_URL com default.
    """
    return os.getenv("DRT_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def admin_credentials():
    """
    Credenciais admin, pula se não definidas.
    """
    email = os.getenv("DRT_ADMIN_EMAIL")
    password = os.getenv("DRT_ADMIN_PASSWORD")
    if not email or not password:
        pytest.skip("Credenciais admin não definidas: DRT_ADMIN_EMAIL e DRT_ADMIN_PASSWORD")
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def http_client():
    """
    Cliente HTTP httpx com timeout e follow_redirects.
    """
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        yield client


@pytest.fixture(scope="session")
def admin_token(http_client, base_url, admin_credentials):
    """
    Token de acesso admin obtido via login real.
    """
    response_data = login_real(http_client, base_url, admin_credentials["email"], admin_credentials["password"])
    return response_data["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    """
    Cabeçalhos para autenticação admin.
    """
    return build_admin_headers(admin_token)


@pytest.fixture(scope="session")
def upload_route(http_client, base_url, admin_headers):
    """
    Rota de upload descoberta.
    """
    return discover_upload_route(http_client, base_url, admin_headers)


@pytest.fixture(scope="function")
def uploaded_test_file_context(http_client, base_url, admin_headers, upload_route):
    """
    Contexto de arquivo de teste enviado: upload, espera indexação, localiza registro.
    """
    filename = f"test_{uuid.uuid4().hex}.pdf"
    pdf_bytes = load_test_pdf_bytes()
    files = {"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    response = http_client.post(f"{base_url}{upload_route}", headers=admin_headers, files=files)
    assert response.status_code in [200, 201], f"Upload falhou: {response.status_code} {response.text}"
    upload_response = response.json()
    time.sleep(2)  # Espera indexação
    file_record = find_uploaded_file_record(http_client, base_url, admin_headers, filename)
    yield {
        "filename": filename,
        "original_file_id": file_record["original_file_id"],
        "file_record": file_record,
        "upload_response": upload_response
    }
    # Cleanup opcional, mas não implementado aqui para evitar destruição


# Testes

def test_integration_health(http_client, base_url):
    """
    Testa endpoint /health, aceitando status 'ok' ou 'online'.
    """
    response = http_client.get(f"{base_url}/health")
    response.raise_for_status()
    data = response.json()
    assert data.get("status") in ["ok", "online"]


def test_integration_login(http_client, base_url, admin_credentials):
    """
    Testa login, validando presença de access_token.
    """
    data = login_real(http_client, base_url, admin_credentials["email"], admin_credentials["password"])
    assert "access_token" in data


def test_integration_chat_authenticated(http_client, base_url, admin_headers):
    """
    Testa chat autenticado, enviando mensagem simples.
    """
    message = os.getenv("DRT_TEST_CHAT_MESSAGE", "O que e piscicultura?")
    payload = {"message": message, "history": []}
    response = http_client.post(f"{base_url}/consultoria/chat", headers=admin_headers, json=payload)
    response.raise_for_status()
    data = response.json()
    assert "answer" in data or "response" in data


def test_integration_upload_pdf(http_client, base_url, admin_headers, upload_route):
    """
    Testa upload de PDF isoladamente.
    """
    filename = f"upload_test_{uuid.uuid4().hex}.pdf"
    pdf_bytes = load_test_pdf_bytes()
    files = {"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    response = http_client.post(f"{base_url}{upload_route}", headers=admin_headers, files=files)
    assert response.status_code in [200, 201]


def test_integration_vector_files_list(http_client, base_url, admin_headers):
    """
    Testa listagem de arquivos vetoriais, validando que é lista.
    """
    response = http_client.get(f"{base_url}/admin/vector-base/files", headers=admin_headers)
    response.raise_for_status()
    data = response.json()
    assert isinstance(data, list)


def test_integration_vector_file_detail(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa detalhe de arquivo vetorial, validando original_file_id.
    """
    file_id = uploaded_test_file_context["original_file_id"]
    response = http_client.get(f"{base_url}/admin/vector-base/files/{file_id}", headers=admin_headers)
    response.raise_for_status()
    data = response.json()
    assert "original_file_id" in data


def test_integration_vector_file_chunks(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa chunks de arquivo vetorial, aceitando lista ou objeto com chunks.
    """
    file_id = uploaded_test_file_context["original_file_id"]
    response = http_client.get(f"{base_url}/admin/vector-base/files/{file_id}/chunks", headers=admin_headers)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        pass  # Lista direta
    elif isinstance(data, dict) and "chunks" in data:
        pass  # Objeto com campo chunks
    else:
        pytest.fail("Resposta inesperada para chunks")


def test_integration_vector_file_content(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa conteúdo de arquivo vetorial, validando presença de content ou chunks.
    """
    file_id = uploaded_test_file_context["original_file_id"]
    response = http_client.get(f"{base_url}/admin/vector-base/files/{file_id}/content", headers=admin_headers)
    response.raise_for_status()
    data = response.json()
    assert "content" in data or "chunks" in data


def test_integration_vector_file_diagnosis(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa diagnóstico de arquivo vetorial, validando status ou flags.
    """
    file_id = uploaded_test_file_context["original_file_id"]
    response = http_client.get(f"{base_url}/admin/vector-base/files/{file_id}/diagnosis", headers=admin_headers)
    response.raise_for_status()
    data = response.json()
    assert "status" in data or any(k.startswith("flag") for k in data.keys())


def test_integration_vector_file_reindex_optional(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa reindexação opcional, pula se não destrutivo.
    """
    if os.getenv("DRT_RUN_DESTRUCTIVE_TESTS", "false").lower() != "true":
        pytest.skip("Teste destrutivo desabilitado: DRT_RUN_DESTRUCTIVE_TESTS != true")
    file_id = uploaded_test_file_context["original_file_id"]
    payload = {"confirmation_phrase": "CONFIRMAR_REINDEXACAO", "original_file_ids": [file_id]}
    response = http_client.post(f"{base_url}/admin/vector-base/reindex", headers=admin_headers, json=payload)
    if response.status_code == 404:
        pytest.skip("Endpoint de reindexação não encontrado")
    response.raise_for_status()


def test_integration_vector_file_delete_optional(http_client, base_url, admin_headers, uploaded_test_file_context):
    """
    Testa exclusão opcional, pula se não destrutivo.
    """
    if os.getenv("DRT_RUN_DESTRUCTIVE_TESTS", "false").lower() != "true":
        pytest.skip("Teste destrutivo desabilitado: DRT_RUN_DESTRUCTIVE_TESTS != true")
    file_id = uploaded_test_file_context["original_file_id"]
    payload = {"confirmation_phrase": "CONFIRMAR_EXCLUSAO", "reason": "teste de integração", "hard_delete": True}
    response = http_client.post(f"{base_url}/admin/vector-base/files/{file_id}/delete", headers=admin_headers, json=payload)
    if response.status_code == 404:
        pytest.skip("Endpoint de exclusão não encontrado")
    response.raise_for_status()


def test_integration_vector_cleanup_optional(http_client, base_url, admin_headers):
    """
    Testa limpeza total opcional, pula se não permitido.
    """
    if (os.getenv("DRT_RUN_DESTRUCTIVE_TESTS", "false").lower() != "true" or
        os.getenv("DRT_ALLOW_CLEANUP", "false").lower() != "true"):
        pytest.skip("Teste de limpeza desabilitado: DRT_RUN_DESTRUCTIVE_TESTS ou DRT_ALLOW_CLEANUP != true")
    payload = {"confirmation_phrase": "CONFIRMAR_LIMPEZA_TOTAL"}
    response = http_client.post(f"{base_url}/admin/vector-base/cleanup", headers=admin_headers, json=payload)
    if response.status_code == 404:
        pytest.skip("Endpoint de limpeza não encontrado")
    response.raise_for_status()