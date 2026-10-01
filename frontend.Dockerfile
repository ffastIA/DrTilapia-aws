# syntax=docker/dockerfile:1
# Build context: raiz do repositório (ver docker-compose.yml — `context: .`).

# ---------- Stage 1: dependências ----------
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package*.json ./
# CA bundle opcional (secret `ca_bundle`, ver stage builder): atrás de proxy
# corporativo com inspeção TLS, `npm ci` falha sem ele. Sem o secret, idêntico a antes.
RUN --mount=type=secret,id=ca_bundle,mode=0444 \
    if [ -s /run/secrets/ca_bundle ]; then \
        NODE_EXTRA_CA_CERTS=/run/secrets/ca_bundle npm ci; \
    else \
        npm ci; \
    fi

# ---------- Stage 2: build ----------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
# NEXT_PUBLIC_* são inlinadas pelo compilador do Next.js em build-time (em
# todo código que ele compila, inclusive middleware.ts) — precisam existir
# aqui, não só como env de runtime do container.
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
# BACKEND_INTERNAL_URL também precisa ser build-time, não runtime: em
# `output: 'standalone'`, a função `rewrites()` de next.config.js roda
# durante `next build` e o destino resolvido é congelado em
# `.next/routes-manifest.json` — o server.js gerado NÃO reavalia
# next.config.js a cada request. Definir isso só como env do container
# (sem rebuild) não tem efeito nenhum sobre o proxy /api-proxy/*.
ARG BACKEND_INTERNAL_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
# `next build` baixa o Google Fonts (next/font) — atrás de proxy corporativo/
# antivírus com inspeção TLS isso falha com "unable to verify the first
# certificate". O CA bundle vem por BuildKit secret mount opcional (mesmo id
# `ca_bundle` do backend.Dockerfile): não entra em camada nenhuma, e sem o
# secret (build na AWS/CI) roda `npm run build` padrão, idêntico a antes.
RUN --mount=type=secret,id=ca_bundle,mode=0444 \
    if [ -s /run/secrets/ca_bundle ]; then \
        NODE_EXTRA_CA_CERTS=/run/secrets/ca_bundle NODE_OPTIONS=--max-old-space-size=1536 npm run build; \
    else \
        NODE_OPTIONS=--max-old-space-size=1536 npm run build; \
    fi

# ---------- Stage 3: runtime (output standalone) ----------
FROM node:20-alpine AS runner
WORKDIR /app

# CA bundle opcional (secret `ca_bundle`) só para o `apk add`: atrás de proxy
# corporativo com inspeção TLS ele falha com "server certificate not trusted".
# SSL_CERT_FILE vale só neste RUN; o certificado não entra em nenhuma camada.
RUN --mount=type=secret,id=ca_bundle,mode=0444 \
    addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs \
    && if [ -s /run/secrets/ca_bundle ]; then \
        SSL_CERT_FILE=/run/secrets/ca_bundle apk add --no-cache curl; \
    else \
        apk add --no-cache curl; \
    fi

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `output: 'standalone'` (frontend/next.config.js) gera um servidor Node
# autocontido em .next/standalone, com só as dependências realmente usadas —
# não precisamos copiar node_modules completo para a imagem final.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
