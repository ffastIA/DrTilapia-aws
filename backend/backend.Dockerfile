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

# Pré-baixa o modelo de remoção de fundo (rembg/u2net, ~176MB) no build da
# imagem, não em tempo de execução — sem isso, a primeira análise de imagem
# depois de cada subida do container dispara esse download em pleno request,
# demorando o suficiente para estourar o timeout do cliente (a análise
# terminava com sucesso no backend, só que depois de o usuário já ver um
# erro). Nome do modelo fixado em REMBG_MODEL
# (backend/app/services/image_processing_service.py) — mudar um sem o outro
# quebra esse cache.
#
# SSL_CERT_FILE/REQUESTS_CA_BUNDLE só neste RUN (não como ENV persistente da
# imagem): o download usa `requests`, que só respeita REQUESTS_CA_BUNDLE, e em
# máquinas atrás do proxy corporativo de inspeção TLS esse download falha com
# CERTIFICATE_VERIFY_FAILED sem essa CA. O bundle vem por BuildKit secret
# mount (--mount=type=secret), não por COPY: assim o certificado do proxy
# nunca é gravado em nenhuma camada da imagem, e a imagem final publicável
# (a que vai para o ECR/AWS) não carrega esse arquivo específico do Windows.
# O secret é opcional (`required` não declarado = false): sem ele — caso de
# builds fora do proxy corporativo, ex. AWS — o comando roda normalmente com
# a verificação TLS padrão (certifi). Fornecido via `docker-compose.yml`
# (`build.secrets: [ca_bundle]`) ou `docker build --secret
# id=ca_bundle,src=backend/ca-bundle-windows.pem`.
RUN --mount=type=secret,id=ca_bundle,mode=0444 \
    if [ -s /run/secrets/ca_bundle ]; then \
        SSL_CERT_FILE=/run/secrets/ca_bundle REQUESTS_CA_BUNDLE=/run/secrets/ca_bundle \
        python -c "from rembg import new_session; new_session('u2net')"; \
    else \
        python -c "from rembg import new_session; new_session('u2net')"; \
    fi

EXPOSE 8000

# /health é um endpoint de liveness dedicado, sem autenticação — /docs deixou
# de servir para isso desde que a spec `auth-endpoint-hardening` passou a
# desabilitá-lo fora de ENVIRONMENT=development.
#
# start-period generoso: com --workers 4, cada worker reimporta toda a
# cadeia pesada (langchain/langgraph/numba/onnxruntime) — medido ~100-110s
# até o último worker log "Application startup complete." em hardware comum.
HEALTHCHECK --interval=15s --timeout=5s --start-period=150s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Sem --reload (modo dev) e com múltiplos workers para paralelismo real.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
