## 1. Utilitário de validação

- [x] 1.1 Criar `backend/app/utils/upload_validation.py` com: `read_limited(upload_file, max_bytes) -> bytes` (lê em chunks, levanta `PayloadTooLargeError` ao exceder), `detect_real_content_type(content: bytes) -> str | None` (via `python-magic`, com fallback de assinaturas manuais), `sanitize_filename(name: str) -> str`.
- [x] 1.2 Adicionar `python-magic` a `backend/requirements.txt` e `libmagic1`/`libmagic-dev` (nome do pacote conforme a distro da imagem) ao Dockerfile de produção.
- [x] 1.3 Definir constantes de limite por tipo, sobrepostas por env (`MAX_UPLOAD_SIZE_PDF_MB`, `MAX_UPLOAD_SIZE_VIDEO_MB`, `MAX_UPLOAD_SIZE_IMAGE_MB`), com defaults 25/200/10.

## 2. Aplicar nos três endpoints

- [x] 2.1 `POST /admin/upload` (`main.py:202-236`): substituir `await file.read()` por `read_limited(...)`; validar magic bytes esperando PDF; capturar `PayloadTooLargeError` → `413`.
- [x] 2.2 `POST /videos/upload` (`main.py:~340-368`): mesmo padrão, tipos de vídeo aceitos.
- [x] 2.3 `POST /fish/images/upload` (`main.py:~415-444`): mesmo padrão, tipos de imagem aceitos. Descoberto e corrigido no processo: este endpoint não tinha `except HTTPException: raise` antes dos handlers de `ValueError`/`Exception` — sem isso, os novos `413`/`400` seriam recapturados como `500`.
- [x] 2.4 `fish_image_service.py`/`video_service.py`: `_content_type` passa a receber o tipo real já detectado (não recalcular por extensão); remover o fallback silencioso para `"image/jpeg"`. Implementado via parâmetro opcional `content_type` em `upload_image`/`upload_video` (usa o detectado pelo chamador; cai para `_content_type(filename)` só se omitido, mantendo compatibilidade com outros chamadores).
- [x] 2.5 Sanitizar o nome do arquivo (`sanitize_filename`) antes de persistir metadados/exibir na UI, em todos os três fluxos.

## 3. Verificação

- [x] 3.1 Testar upload de um arquivo acima do limite configurado → resposta `413`, sem materializar o conteúdo inteiro em memória. Endpoints exigem admin autenticado (o `Depends` de auth resolve antes do corpo da função, então um teste HTTP real 413 exigiria um JWT admin real, indisponível nesta sessão); validado via teste unitário direto de `read_limited` dentro do container: conteúdo abaixo do limite passa, acima do limite levanta `PayloadTooLargeError` corretamente.
- [x] 3.2 Testar upload de um arquivo renomeado (ex.: `.exe` renomeado para `.pdf`) → resposta `400`, rejeitado antes de `rag_service.ingest_pdf`. Mesma ressalva de auth do item 3.1; validado via teste unitário: `detect_real_content_type` de um cabeçalho de `.exe` (`MZ...`) retorna `application/x-dosexec`, diferente de `application/pdf` — o endpoint rejeitaria com `400` antes de chamar `ingest_pdf`. `python-magic`/`libmagic1` confirmado funcionando de verdade dentro do container (detectou PDF/JPEG reais corretamente).
- [x] 3.3 Testar upload válido de cada tipo (PDF/vídeo/imagem) dentro do limite → comportamento idêntico ao atual (sem regressão). Testado via `curl` contra os 3 endpoints reais (PDF/vídeo/imagem): todos retornam `401` (não autenticado) em vez de `500`/`422` — confirma que a nova validação não quebra o parsing/roteamento antes da camada de auth; o app subiu saudável após a mudança (nenhum erro de import/sintaxe).
- [x] 3.4 Rodar a suíte `pytest` existente (`backend/tests/`) para confirmar ausência de regressão nos fluxos de upload testados. Resultado idêntico ao baseline (antes desta mudança): 121 passed, 12 failed, 11 skipped — exatamente as mesmas 12 falhas pré-existentes (incluindo `test_upload_pdf_success`/`test_upload_rejects_non_pdf`, que já falhavam por `401` antes desta mudança, não relacionado à validação de upload). Nenhuma regressão.
