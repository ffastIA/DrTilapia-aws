## Context

`backend/app/services/rag_service.py` importa `fitz` (PyMuPDF) no topo, dentro de um `try/except ImportError` que define `_PYMUPDF_AVAILABLE`. Esse import carrega os binários nativos do MuPDF a cada subida do uvicorn. O PyMuPDF só é usado para renderizar páginas em imagem nos estágios 3 (Tesseract) e 4 (Vision OCR) da cascata de extração, que só rodam quando `pypdf` e `pdfplumber` falham (PDF escaneado). Ambos os métodos (`_extract_text_via_tesseract`, `_extract_text_via_vision`) já fazem seu próprio `import fitz as pymupdf` local.

A EC2 do backend tem 1 GB de RAM, e o servidor não consegue subir por falta de memória.

## Goals / Non-Goals

**Goals:**
- Importar `rag_service` sem carregar o módulo `fitz`.
- Manter `_PYMUPDF_AVAILABLE` com o mesmo significado, e a cascata de extração com o mesmo comportamento.

**Non-Goals:**
- Alterar `rembg`, `cv2`, `pdfplumber`, `pytesseract` ou qualquer outra dependência. A remoção de fundo de imagens é usada com frequência e deve continuar pronta.
- Trocar o PyMuPDF por outra biblioteca de renderização.
- Reduzir o pico de memória durante o OCR de um PDF escaneado.
- Configurar swap ou limites de memória no host/compose.

## Decisions

**Usar `importlib.util.find_spec("fitz")` para definir `_PYMUPDF_AVAILABLE`.**
`find_spec` localiza o pacote sem executá-lo nem carregá-lo em `sys.modules`, e devolve `None` se não estiver instalado. Preserva a semântica atual do flag com custo de memória desprezível.
Alternativas descartadas:
- *Remover o flag e deixar o `import` falhar dentro das funções*: mudaria a cascata, pois o `if _PYMUPDF_AVAILABLE` decide se o estágio é tentado e o aviso da linha ~574 depende dele.
- *Import preguiçoso com cache em função `_get_fitz()`*: mais código sem benefício, já que os métodos importam localmente e o Python cacheia módulos em `sys.modules`.

**Manter o `import fitz` local nos dois extratores.** Já existe hoje, então nenhuma mudança é necessária.

**Diferença aceita**: `find_spec` confirma que o pacote está instalado, mas não que o import funcionará (por exemplo, binário nativo corrompido). Nesse caso a falha ocorre no momento do OCR e cai no `except Exception` já existente na cascata (linhas ~569 e ~591), que registra o erro e segue adiante.

## Risks / Trade-offs

- [O pico de memória durante o OCR de PDF escaneado permanece, e pode causar OOM em 1 GB] → Fora do escopo; mitigar com swap e limite de memória no host, tratados separadamente.
- [`find_spec` retorna não-`None` para pacote quebrado, mudando quando a falha aparece] → A falha vira exceção capturada na cascata, que já trata esse caso e segue para o próximo estágio.
- [Um teste que dependa de `rag_service.fitz` ou `_fitz` quebraria] → O nome `_fitz` só existe no bloco de import; conferir com busca no código e nos testes antes de remover.
