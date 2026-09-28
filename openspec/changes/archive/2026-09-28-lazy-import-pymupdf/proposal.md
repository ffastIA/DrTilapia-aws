## Why

O backend não sobe na EC2 de 1 GB por falta de memória. `rag_service.py` executa `import fitz` (PyMuPDF) no topo do módulo, carregando as bibliotecas nativas do MuPDF na subida do uvicorn, embora o PyMuPDF só seja necessário nos estágios de OCR (Tesseract e Vision) da cascata de extração de PDF, acionados apenas para PDFs escaneados.

## What Changes

- Substituir o `try: import fitz ... except ImportError` do topo de `backend/app/services/rag_service.py` por uma verificação de disponibilidade via `importlib.util.find_spec("fitz")`, que não carrega o módulo.
- `_PYMUPDF_AVAILABLE` continua existindo e com o mesmo significado (pacote instalado), mas deixa de custar memória na importação.
- O `import fitz` real permanece apenas dentro de `_extract_text_via_tesseract` e `_extract_text_via_vision`, executado só quando o OCR é necessário.
- Fora do escopo: `rembg`, `cv2` e demais dependências, pois a remoção de fundo de imagens é usada com frequência e precisa estar pronta.

## Capabilities

### New Capabilities
- `pdf-ocr-lazy-dependencies`: o PyMuPDF só é carregado em memória quando um estágio de OCR de PDF o exige, não na subida do servidor.

### Modified Capabilities

## Impact

- Código: `backend/app/services/rag_service.py` (bloco de imports, linhas ~25-29).
- Testes: novo teste em `backend/tests/` para importação sem `fitz` e para a cascata de extração.
- Comportamento funcional da cascata de extração: inalterado.
- Dependências: nenhuma adicionada ou removida; `pymupdf` continua em `requirements.txt`.
- Operação: reduz o pico de memória na subida; o pico durante o OCR de PDF escaneado permanece.
