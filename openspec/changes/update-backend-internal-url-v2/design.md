## Context

O frontend repassa `/api-proxy/*` ao backend FastAPI por um `rewrites()` do Next.js
(`frontend/next.config.js`). Com `output: 'standalone'`, o destino é calculado durante `next build` e
congelado em `.next/routes-manifest.json`: mudar a variável de ambiente do container não tem efeito.
Por isso `BACKEND_INTERNAL_URL` é um `ARG` do `frontend.Dockerfile`, preenchido por
`deploy/build-and-push.ps1`.

Histórico de endereços do backend de produção:

| Instância | Estado | IP privado | Sub-rede |
|---|---|---|---|
| `tilapia-backend` (`i-0d2ef8379a4c4c0cd`) | stopped | `10.1.20.128` | `subnet-01e63a71dc2c8ab51` |
| `tilapia-backend-v2` (`i-0eeca103e61379d4b`) | running (lançada 2026-10-01 09:57 UTC) | `10.1.2.22` | `subnet-0111a878e18f11a95` |

Ambas usam o Security Group `sg-0857384097046e629`, que permite TCP 8000 vindo do Security Group do
frontend (`sg-074ec8eb28509f354`).

## Goals / Non-Goals

**Goals:**
- Restaurar o login e todas as chamadas ao backend em produção, apontando a imagem para `10.1.2.22`.
- Deixar registrado o diagnóstico e uma verificação pós-deploy que detecte esse problema em segundos.

**Non-Goals:**
- Eliminar a dependência de IP fixo (DNS interno, Application Load Balancer interno, Route 53 privado).
  É a correção durável, mas muda a topologia; fica como follow-up.
- Alterar timeouts do CloudFront ou do Nginx.

## Decisions

### 1. Manter o endereço como constante do script de build
O valor continua declarado diretamente em `deploy/build-and-push.ps1` (requisito já existente: o build de
produção não herda valores do `docker-compose.yml`). Troca-se apenas o IP.

### 2. Verificar pelo caminho completo após o deploy
`GET https://<dominio-cloudfront>/api-proxy/health` percorre CloudFront → Nginx → Next.js → backend. Se
responde `{"status":"ok"}` em poucos segundos, o endereço gravado está correto e alcançável; se fica
pendurado até o `OriginReadTimeout` (55 s) e vira 504, o endereço gravado aponta para um host
inexistente, parado ou bloqueado. Testes só nas páginas do frontend (`/`, `/auth/login`) **não** detectam
o problema.

### 3. Frontend e backend são reconstruídos/atualizados em separado
Só a imagem do frontend muda aqui. A imagem do backend (arm64, publicada em 2026-09-30) não é refeita.
Pré-requisito: o container do backend em `tilapia-backend-v2` deve estar rodando essa imagem e responder
`/health`.

## Risks / Trade-offs

- [IP privado muda quando a instância é recriada] → Já aconteceu (`10.1.20.128` → `10.1.2.22`) e se
  repetirá. Mitigação imediata: o requisito de verificação pós-deploy abaixo. Mitigação durável: DNS
  interno ou ALB interno (follow-up).
- [Build arm64 do frontend é pesado neste PC] → Usar `-Builder desktop-linux`, com a memória do Docker
  limitada em `.wslconfig`; só a camada do `next build` é refeita (as dependências estão em cache).
- [Backend v2 sem o container certo] → Confirmar `/health` na instância antes de culpar o frontend.
