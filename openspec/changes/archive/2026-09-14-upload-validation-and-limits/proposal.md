## Why

Os três endpoints de upload (`POST /admin/upload` — PDF, `backend/app/main.py:216`; `POST /videos/upload` — vídeo, `main.py:348`; `POST /fish/images/upload` — imagem, `main.py:422`) leem o corpo inteiro do arquivo em memória via `await file.read()` sem nenhum limite de tamanho configurado. Um cliente autenticado pode enviar um arquivo arbitrariamente grande, esgotando memória/CPU do processo — agravado pelo custo de OCR (`pytesseract`/Vision) e remoção de fundo (`rembg`) por página/imagem, que rodam sobre o conteúdo já materializado.

Além disso, o tipo do arquivo persistido é derivado apenas da **extensão do nome enviado pelo cliente**, nunca dos bytes reais: `backend/app/services/fish_image_service.py:49-51` (`_content_type`) faz `Path(filename).suffix.lower()` → lookup num dicionário de extensões permitidas, e o mesmo padrão existe em `video_service.py`. Renomear um arquivo arbitrário para `.jpg`/`.mp4`/`.pdf` basta para contornar essa validação. O nome original do arquivo também é persistido e reexibido verbatim na UI administrativa, o que é superfície de XSS armazenado se o frontend não escapar o valor ao renderizar.

## What Changes

- Adicionar um limite de tamanho por tipo de upload (PDF, vídeo, imagem — valores configuráveis via variável de ambiente, com um default conservador cada), verificado incrementalmente (streaming) antes de materializar o arquivo inteiro em memória, retornando `413 Payload Too Large` ao exceder.
- Validar o tipo real do arquivo pela assinatura/magic bytes do conteúdo (não pela extensão do nome), rejeitando com `400` quando o conteúdo não corresponde a nenhum tipo permitido para aquele endpoint.
- Sanitizar o nome de arquivo original antes de persistir/reexibir (normalizar Unicode, restringir a um allowlist de caracteres, truncar comprimento) — sem alterar como o *path* de armazenamento é gerado (`_make_storage_path` já usa `uuid4()`, não o nome original).

## Capabilities

### New Capabilities
- `upload-validation-and-limits`: todo upload de arquivo (PDF/vídeo/imagem) tem tamanho e tipo real (magic bytes) validados antes de ser processado ou persistido, e o nome original é sanitizado antes de ser armazenado/reexibido.

## Impact

- **Código afetado**: `backend/app/main.py` (os três endpoints de upload), `backend/app/services/fish_image_service.py` (`_content_type`), `backend/app/services/video_service.py` (equivalente), `backend/app/services/rag_service.py` (recebe o PDF já lido em `upload_admin`) — mais um novo módulo utilitário de validação (ex.: `backend/app/utils/upload_validation.py`).
- **Dependências**: nova dependência para detecção de tipo por conteúdo (ex.: `python-magic`), que exige o binário `libmagic` no ambiente de execução — relevante para o Dockerfile de produção (parte da containerização planejada separadamente).
- **Comportamento observável**: uploads dentro do limite de tamanho e com tipo real correspondente à extensão continuam funcionando sem mudança; uploads acima do limite ou com tipo real divergente passam a ser rejeitados antes do processamento pesado (OCR/rembg), em vez de consumidos silenciosamente.
