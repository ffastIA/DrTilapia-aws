## ADDED Requirements

### Requirement: Importing the RAG service does not load PyMuPDF
Importing `app.services.rag_service` SHALL NOT load the `fitz` (PyMuPDF) module into memory. The module MUST be loaded only when a PDF OCR stage that needs it is executed.

#### Scenario: Server import leaves PyMuPDF unloaded
- **WHEN** `app.services.rag_service` is imported in a fresh Python process
- **THEN** `"fitz"` is not present in `sys.modules`

#### Scenario: PyMuPDF is loaded when OCR runs
- **WHEN** a PDF reaches the Tesseract or Vision OCR extraction stage
- **THEN** the `fitz` module is imported at that moment and used to render pages

### Requirement: PyMuPDF availability is detected without importing it
The system SHALL determine whether PyMuPDF is installed without loading it, and `_PYMUPDF_AVAILABLE` MUST be true if and only if the package is installed.

#### Scenario: Package installed
- **WHEN** PyMuPDF is installed in the environment
- **THEN** `_PYMUPDF_AVAILABLE` is `True` after importing `rag_service`, and `fitz` is still not in `sys.modules`

#### Scenario: Package not installed
- **WHEN** PyMuPDF is not installed in the environment
- **THEN** `_PYMUPDF_AVAILABLE` is `False`, the server starts normally, and no import error is raised

### Requirement: The extraction cascade behavior is unchanged
The PDF extraction cascade SHALL keep its current stage order and gating: the Tesseract stage MUST run only when both PyMuPDF and pytesseract are available, and the Vision stage MUST run only when PyMuPDF is available.

#### Scenario: PyMuPDF unavailable skips OCR stages
- **WHEN** `_PYMUPDF_AVAILABLE` is `False` and `pypdf` and `pdfplumber` fail quality checks
- **THEN** neither the Tesseract nor the Vision stage is attempted, and the warning about unavailable OCR is logged

#### Scenario: OCR stage failure falls through
- **WHEN** an OCR stage raises an error while importing or using PyMuPDF
- **THEN** the error is logged and the cascade continues to the next stage instead of aborting the ingestion
