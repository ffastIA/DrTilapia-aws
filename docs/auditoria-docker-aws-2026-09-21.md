# Auditoria de build Docker → AWS — DrTilapIA - aws

**Data**: 2026-09-21
**Alvo de deploy confirmado**: EC2 Ubuntu com Docker (CloudFront como origin apontando para a instância)
**Escopo**: `backend/`, `frontend/`, `backend.Dockerfile`, `frontend.Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore`, `.gitattributes`, `.env`/`.env.example` de ambos os serviços, histórico completo do Git, build local (`.next`) do frontend.

## Resumo

3 achados, nenhum crítico. O achado crítico da auditoria anterior (CA bundle corporativo entrando na imagem via `COPY`) já foi corrigido — hoje é injetado só por BuildKit secret mount, excluído do `.gitignore` e do `.dockerignore`, e nunca vira camada da imagem. Autenticação, CORS, rate limit e o fechamento de `/docs` fora de desenvolvimento já estão implementados corretamente. O risco real que resta: o frontend público roda em `node:18-alpine` (sem suporte de segurança desde abril/2025), e não existe no repositório nenhum artefato de provisionamento da EC2 (IAM, IMDSv2, security group, rotação de logs).

## Pontos já corretos (verificados, sem ação necessária)

- CA bundle corporativo (`backend/ca-bundle-windows.pem`) excluído do `.gitignore` **e** do `.dockerignore`; nunca foi commitado no histórico do Git.
- `backend.Dockerfile` injeta o CA bundle só via `RUN --mount=type=secret,id=ca_bundle` — não vira camada da imagem.
- Multi-stage build limpo nos dois Dockerfiles; usuário não-root (`appuser` / `nextjs`); `CMD` em forma exec; `apt-get install` + `rm -rf /var/lib/apt/lists/*` na mesma camada.
- `/docs`, `/redoc`, `/openapi.json` fechados por padrão (só abrem com `ENVIRONMENT=development`).
- CORS lido de `ALLOWED_ORIGINS` (lista explícita, nunca `*`), rate limit em `/auth/login` via slowapi.
- Frontend só recebe `NEXT_PUBLIC_SUPABASE_ANON_KEY` (chave anon/pública) — nenhuma `service_role`/`OPENAI_API_KEY` encontrada no bundle `.next` construído.
- Porta do backend publicada só em `127.0.0.1:8000` (loopback); porta do frontend em `0.0.0.0:3000` é intencional (CloudFront → EC2), com a restrição pretendida no Security Group.
- CRLF em `.env`/`backend/.env`: verificado empiricamente que `python-dotenv==1.0.1` já normaliza o `\r` ao carregar — não é risco real neste projeto.

## Achados e ações necessárias

### 1. [ALTO] Frontend roda em Node.js 18, sem suporte de segurança desde 30/04/2025
- **Evidência**: `frontend.Dockerfile:5,11,33` — `FROM node:18-alpine` nos três estágios.
- **Risco**: é o serviço exposto publicamente (porta 3000, CloudFront como origin); CVEs no Node 18 encontradas após abril/2025 não recebem mais patch.
- **Ação**: trocar as três ocorrências de `node:18-alpine` para `node:20-alpine` (Next 14 suporta Node 18.17+/20+, sem mudança de código esperada) e rebuildar.
- **Verificação**: `docker run --rm <imagem> node --version` deve retornar `v20.x`.

### 2. [MÉDIO] Nenhum artefato de provisionamento da EC2 versionado
- **Evidência**: busca por `task-definition*`, `buildspec*`, `*.tf`, `.github/workflows` e READMEs com instruções de deploy — nada encontrado no repositório.
- **Risco**: IAM role/instance profile, IMDSv2, regras do security group e rotação de log existem só no console da AWS (ou na cabeça de quem provisionou) — não são auditáveis nem reproduzíveis a partir do código.
- **Ação**: versionar o script de bootstrap/deploy da instância (pull do ECR + `docker compose up` com as flags reais) e documentar o instance profile IAM usado e a confirmação de IMDSv2.
- **Verificação**: `aws ec2 describe-instances --query 'Reservations[].Instances[].MetadataOptions'` deve mostrar `HttpTokens: required`; o Security Group deve liberar a porta 3000 só para o prefix list `com.amazonaws.global.cloudfront.origin-facing`.

### 3. [MÉDIO] Comentários do projeto se contradizem sobre o alvo de deploy (ECS Fargate vs. EC2)
- **Evidência**: `docker-compose.yml:1-3` diz "ECS Fargate"; `docker-compose.yml:72-76` (porta do frontend) diz "CloudFront aponta pra esta EC2". Alvo real confirmado: EC2.
- **Risco**: pode levar quem revisar depois a aplicar o checklist de segurança errado (execution/task role do Fargate em vez de instance profile de EC2).
- **Ação**: atualizar o comentário do topo do `docker-compose.yml` para refletir EC2.
- **Verificação**: `grep -n "ECS Fargate\|EC2" docker-compose.yml` deve retornar uma descrição única e consistente.

### 4. [BAIXO] `backend/.env` local aponta o CA bundle para um caminho de host desatualizado
- **Evidência**: `backend/.env:18-19` aponta `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` para `...\Aquicultura\DrTilapIA\backend\...` (pasta antiga, antes do projeto ser renomeado para `DrTilapIA - aws`).
- **Risco**: só afeta quem rodar o backend fora do Docker (`uvicorn` direto no Windows) atrás do proxy corporativo — quebra com `CERTIFICATE_VERIFY_FAILED`. Não afeta o container (o `docker-compose.yml` sobrescreve essas variáveis) nem a AWS.
- **Ação**: atualizar as duas linhas em `backend/.env` (arquivo local, não versionado) para incluir `- aws` no caminho.
- **Verificação**: `python -c "from dotenv import dotenv_values; import os; print(os.path.exists(dotenv_values('backend/.env')['SSL_CERT_FILE']))"` deve retornar `True`.

### 5. [BAIXO] Diretório vazio órfão `backend/ca-bundle-windows.pem;C/`
- **Evidência**: diretório vazio, criado hoje, invisível ao Git (diretório vazio) e não coberto pelo `.dockerignore` atual (que só exclui o nome exato `backend/ca-bundle-windows.pem`).
- **Risco**: hoje inofensivo (vazio); o nome sugere um comando/script que interpretou mal um valor com `;` (separador de PATH do Windows).
- **Ação**: remover o diretório (`rmdir`) e investigar qual comando o gerou antes que acumule conteúdo real.
- **Verificação**: `ls backend/ | grep ';'` deve voltar vazio.

## Não verificado

- Conteúdo real do Security Group e do instance profile IAM da EC2 (precisa de acesso ao console/CLI da AWS).
- Camadas reais da imagem Docker (`docker history`, `docker save`) — nenhum Docker daemon disponível no ambiente de auditoria; avaliação feita por leitura estática dos Dockerfiles.
- Permissão do arquivo `.env` no host EC2 (deveria ser `600`).
- Vulnerabilidades por CVE nas dependências Python/Node via scanner (`trivy`/`docker scout`) — não executado (exige imagem construída).

## Ordem de execução sugerida

1. **Achado 1** (Node 18 → 20) — único com exposição pública direta.
2. **Achado 2** (documentar provisionamento da EC2) — resolve também a ambiguidade do achado 3.
3. **Achado 3** (corrigir comentário ECS Fargate → EC2).
4. **Achados 4 e 5** — ajustes rápidos, sem risco, a qualquer momento.
