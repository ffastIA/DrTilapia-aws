## Context

`backend/app/main.py:214-217` (PDF):
```python
with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
    temp_path = temp_file.name
    content = await file.read()
    temp_file.write(content)
```
Mesmo padrão em `main.py:348` (vídeo) e `main.py:422` (imagem) — `await file.read()` sem argumento de tamanho, e sem checagem prévia de `Content-Length`/tamanho incremental.

`backend/app/services/fish_image_service.py:49-51`:
```python
def _content_type(self, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ALLOWED_EXTENSIONS.get(ext, "image/jpeg")
```
Note o fallback silencioso para `"image/jpeg"` quando a extensão não está no dicionário — nem sequer rejeita extensões desconhecidas, apenas assume um tipo.

## Goals / Non-Goals

**Goals:**
- Limite de tamanho por tipo de upload, aplicado antes de processamento pesado (OCR/rembg).
- Validação de tipo por conteúdo real (magic bytes), não por extensão do nome.
- Nome de arquivo sanitizado antes de persistir/reexibir.

**Non-Goals:**
- Não configurar limite de tamanho na camada de infraestrutura (ALB/API Gateway) — isso é tratado na parte de containerização/infra AWS deste projeto, como camada adicional de defesa, não substituto desta validação em nível de aplicação.
- Não adicionar scanning de malware/antivírus — fora de escopo desta mudança pontual.
- Não alterar o esquema de nomeação do *path* de storage (já é `uuid4()`-based, não usa o nome original).

## Decisions

1. **Checagem de tamanho via streaming em chunks** (`UploadFile.read(chunk_size)` em loop, abortando cedo ao ultrapassar o limite) em vez de confiar apenas no header `Content-Length` (que pode ser omitido/forjado pelo cliente) — garante que o limite é respeitado mesmo sem o header.
2. **Detecção de tipo por magic bytes via `python-magic`** (binding para `libmagic`), por ser a abordagem padrão de mercado; caso `libmagic` não esteja disponível no ambiente de execução (ex.: falha de instalação), cair para uma checagem manual das assinaturas mais comuns (`%PDF-` para PDF; cabeçalhos JPEG/PNG/WebP para imagem; `ftyp`/EBML para os contêineres de vídeo aceitos) documentada como fallback, nunca aceitar silenciosamente sem nenhuma checagem.
3. **Sanitização do nome**: normalizar Unicode (NFKC), permitir apenas um allowlist de caracteres (alfanuméricos, `-_. `), truncar em um comprimento máximo razoável (ex.: 200 caracteres) preservando a extensão — aplicado no momento de gravar o metadado do arquivo, não no *path* físico de storage.
4. **Limites default sugeridos** (configuráveis via env, para não travar o código a um valor arbitrário): PDF 25MB, vídeo 200MB, imagem 10MB — alinhados à natureza de cada tipo de conteúdo e aos custos de processamento (OCR por página, `rembg` por imagem).

## Risks / Trade-offs

- **[Trade-off]** Um limite de tamanho pode rejeitar uploads legítimos maiores que o esperado por algum usuário — mitigado tornando os limites configuráveis via variável de ambiente, ajustável sem redeploy de código.
- **[Risco operacional]** `python-magic`/`libmagic` precisa estar instalado no ambiente de execução (SO) — deve ser adicionado explicitamente ao Dockerfile de produção; sem isso, o fallback manual de assinaturas cobre os tipos hoje aceitos, mas com uma superfície de detecção mais estreita.
