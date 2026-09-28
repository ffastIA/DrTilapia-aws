# CAMINHO: backend/tests/test_pymupdf_lazy_import.py
"""Testes de `lazy-import-pymupdf`: o PyMuPDF (`fitz`) não pode ser carregado
na importação de `rag_service` (a EC2 tem 1 GB), só quando um estágio de OCR
o exige — e a cascata de extração precisa se comportar como antes.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_service import get_rag_service

# `app.services.rag_service` aparece no pacote como um proxy do serviço; o módulo
# real, com as flags e imports, só é acessível por `sys.modules`.
rag_module = sys.modules["app.services.rag_service"]

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_isolated(code: str) -> str:
    """Executa `code` em um processo limpo — `sys.modules` deste processo de
    teste já pode ter o `fitz` carregado por outro teste."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_importing_rag_service_does_not_load_fitz():
    out = _run_isolated(
        "import sys; import app.services.rag_service; print('fitz' in sys.modules)"
    )
    assert out.splitlines()[-1] == "False"


@pytest.mark.skipif(
    importlib.util.find_spec("fitz") is None, reason="PyMuPDF não instalado"
)
def test_flag_true_when_installed_without_importing_it():
    out = _run_isolated(
        "import sys; import app.services.rag_service; m = sys.modules['app.services.rag_service']; "
        "print(m._PYMUPDF_AVAILABLE, 'fitz' in sys.modules)"
    )
    assert out.splitlines()[-1] == "True False"


def test_flag_false_when_not_installed():
    code = (
        "import importlib.util as u, sys\n"
        "real = u.find_spec\n"
        "u.find_spec = lambda name, *a, **k: None if name == 'fitz' else real(name, *a, **k)\n"
        "import app.services.rag_service\n"
        "print(sys.modules['app.services.rag_service']._PYMUPDF_AVAILABLE)"
    )
    assert _run_isolated(code).splitlines()[-1] == "False"


@pytest.fixture
def service():
    return get_rag_service()


def _no_text_pdf_stages(monkeypatch, service, *, pymupdf: bool, tesseract: bool):
    """Deixa pypdf/pdfplumber sem produzir texto e expõe os extratores de OCR
    como mocks, para observar o gating da cascata."""
    loader = MagicMock()
    loader.load.return_value = []
    monkeypatch.setattr(rag_module, "PyPDFLoader", lambda path: loader)
    monkeypatch.setattr(rag_module, "_PDFPLUMBER_AVAILABLE", False)
    monkeypatch.setattr(rag_module, "_PYMUPDF_AVAILABLE", pymupdf)
    monkeypatch.setattr(rag_module, "_PYTESSERACT_AVAILABLE", tesseract)
    tess = MagicMock(return_value=[])
    vision = MagicMock(return_value=[])
    monkeypatch.setattr(service, "_extract_text_via_tesseract", tess)
    monkeypatch.setattr(service, "_extract_text_via_vision", vision)
    return tess, vision


def test_cascade_skips_ocr_stages_without_pymupdf(monkeypatch, service, caplog):
    tess, vision = _no_text_pdf_stages(monkeypatch, service, pymupdf=False, tesseract=True)

    with caplog.at_level("WARNING"):
        _, method, quality = service._load_pdf_with_fallback("x.pdf", "x.pdf")

    tess.assert_not_called()
    vision.assert_not_called()
    assert method == "pypdf"
    assert not quality.adequate
    assert "Tesseract indisponível" in caplog.text


def test_cascade_tesseract_needs_pytesseract_but_vision_only_pymupdf(monkeypatch, service):
    tess, vision = _no_text_pdf_stages(monkeypatch, service, pymupdf=True, tesseract=False)

    service._load_pdf_with_fallback("x.pdf", "x.pdf")

    tess.assert_not_called()
    vision.assert_called_once()


def test_cascade_continues_when_ocr_stage_fails_to_import_fitz(monkeypatch, service, caplog):
    tess, vision = _no_text_pdf_stages(monkeypatch, service, pymupdf=True, tesseract=True)
    tess.side_effect = ImportError("No module named 'fitz'")
    vision.side_effect = ImportError("No module named 'fitz'")

    with caplog.at_level("WARNING"):
        _, method, quality = service._load_pdf_with_fallback("x.pdf", "x.pdf")

    tess.assert_called_once()
    vision.assert_called_once()
    assert method == "pypdf"
    assert not quality.adequate
    assert "Tesseract OCR falhou" in caplog.text
