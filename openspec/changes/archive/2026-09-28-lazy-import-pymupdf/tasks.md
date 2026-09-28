## 1. Preparação

- [x] 1.1 Buscar no código e nos testes referências a `_fitz` e a `rag_service.fitz` para confirmar que nada além do bloco de import as usa
- [x] 1.2 Medir o RSS de `import app.services.rag_service` antes da mudança (linha de base: +308 MB, `fitz` carregado)

## 2. Implementação

- [x] 2.1 Em `backend/app/services/rag_service.py` (linhas ~25-29), substituir o `try: import fitz as _fitz ... except ImportError` por `_PYMUPDF_AVAILABLE = importlib.util.find_spec("fitz") is not None`, adicionando `import importlib.util`
- [x] 2.2 Confirmar que `_extract_text_via_tesseract` e `_extract_text_via_vision` mantêm o `import fitz as pymupdf` local e que a cascata (linhas ~560-592) não foi alterada
- [x] 2.3 Confirmar que `rembg`, `cv2` e demais imports do topo não foram tocados

## 3. Testes

- [x] 3.1 Criar teste em `backend/tests/` que importa `app.services.rag_service` em subprocesso limpo e verifica `"fitz" not in sys.modules`
- [x] 3.2 Criar teste de `_PYMUPDF_AVAILABLE` com `find_spec` simulado retornando `None` e um spec válido
- [x] 3.3 Criar teste da cascata com `_PYMUPDF_AVAILABLE` falso: os estágios Tesseract e Vision não são tentados e o aviso é registrado
- [x] 3.4 Criar teste em que o estágio de OCR falha ao importar/usar o `fitz`: o erro é registrado e a cascata continua
- [x] 3.5 Rodar a suíte existente (`pytest backend/tests`) e confirmar que não há regressões

## 4. Validação

- [x] 4.1 Medir o RSS do import após a mudança e comparar com a linha de base de 1.2 (resultado: +286 MB, `fitz` não carregado; economia de ~22 MB, pois o grosso do consumo vem de langchain e demais dependências)
- [ ] 4.2 Ingerir um PDF de texto (caminho `pypdf`) e um PDF escaneado (força o OCR) e confirmar que ambos funcionam
- [ ] 4.3 Subir o container com limite de 1 GB e confirmar que o uvicorn inicia e responde
