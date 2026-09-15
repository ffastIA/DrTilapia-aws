## Why

`POST /fish/analyses/process` (usado por `/main/images`, "Análise de Imagens por IA") retornava sempre `500`. Investigado ao vivo (`docker compose logs backend` durante uma reprodução real no navegador, com imagens fornecidas pelo usuário):

**Causa raiz 1 (crash real do processo, não uma exceção Python normal):** `ImageProcessingService.remove_background` chama `rembg.remove(image_bytes)` **sem fixar o modelo**. `requirements.txt` pina só `rembg[cpu]>=2.0.50` (sem teto). Na versão instalada (`2.0.84`), o modelo *default* da lib mudou de `u2net` (~176MB, o que o docstring do serviço sempre disse usar) para `bria-rmbg` (~1GB) — sem nenhuma mudança de código aqui. Rodar `bria-rmbg` **derruba o processo worker do uvicorn** (log mostra `Waiting for child process [N]` / `Child process [N] died`, sem nenhum traceback Python capturável — é um crash nativo do onnxruntime, não uma exceção). O cliente recebe `500` porque o worker que atendia a requisição simplesmente sumiu.

**Causa raiz 2 (timeout, descoberta ao corrigir a 1ª):** fixar o modelo em `u2net` resolve o crash, mas `rembg` baixa esse modelo (176MB) **lazily, na primeira chamada em tempo de execução** — o download demora ~30-40s, e a requisição estourava o timeout do lado do cliente antes de terminar (o backend, sozinho, terminava a análise com sucesso ~10-15s **depois** de o navegador já ter mostrado erro).

## What Changes

- `backend/app/services/image_processing_service.py`: modelo do `rembg` fixado explicitamente via `REMBG_MODEL` (env, default `u2net`), com uma sessão cacheada (`_get_rembg_session()`) em vez de deixar a lib escolher/recarregar a cada chamada.
- `backend/backend.Dockerfile`: novo passo de build (`RUN python -c "from rembg import new_session; new_session('u2net')"`, depois de `USER appuser`) — baixa e cacheia o modelo **na imagem**, não em tempo de execução. Elimina o delay/timeout da primeira análise depois de cada subida do container.
- `backend/.env.example`: documentado `REMBG_MODEL=u2net`, com o histórico do porquê não trocar sem testar.

## Capabilities

### New Capabilities
- `fish-image-analysis-resilience`: a análise de imagem de peixe (remoção de fundo via IA) usa um modelo fixado e pré-carregado, não o default móvel de uma dependência externa, evitando crash de processo e delay de primeira requisição.

## Impact

- **Código afetado**: `image_processing_service.py` (pin de modelo + sessão cacheada), `backend.Dockerfile` (pré-download em build), `.env.example` (documentação).
- **Build**: a imagem do backend cresce ~176MB (modelo `u2net` embutido) e o build passa a precisar de acesso à internet para baixá-lo (já era o caso para `pip install`).
- **Comportamento observável**: `POST /fish/analyses/process` funciona corretamente já na primeira chamada depois de qualquer subida do container, sem crash e sem delay de download.
