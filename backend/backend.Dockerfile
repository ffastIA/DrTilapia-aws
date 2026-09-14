# syntax=docker/dockerfile:1
# Build context: raiz do repositório (ver docker-compose.yml — `context: .`).

# ---------- Stage 1: build das dependências Python ----------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Stage 2: imagem de runtime ----------
FROM python:3.11-slim AS runtime

WORKDIR /app/backend

# Dependências de sistema exigidas em runtime (ausentes na imagem anterior):
# - libpq5: cliente Postgres (runtime da lib usada em build)
# - tesseract-ocr / poppler-utils: fallback de OCR do pipeline de ingestão de PDF
# - libgl1 / libglib2.0-0: exigidas por opencv-contrib-python e rembg
# - libmagic1: exigida por python-magic (detecção de tipo real de upload)
# - curl: usado pelo HEALTHCHECK abaixo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY backend/ /app/backend/

RUN chown -R appuser:appuser /app /home/appuser/.local

ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Endpoint de docs do FastAPI existe hoje por padrão; se/quando a spec
# `auth-endpoint-hardening` desabilitar /docs fora de ambiente de
# desenvolvimento, trocar este alvo por um endpoint /health dedicado.
#
# start-period generoso: com --workers 4, cada worker reimporta toda a
# cadeia pesada (langchain/langgraph/numba/onnxruntime) — medido ~100-110s
# até o último worker log "Application startup complete." em hardware comum.
HEALTHCHECK --interval=15s --timeout=5s --start-period=150s --retries=5 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Sem --reload (modo dev) e com múltiplos workers para paralelismo real.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
