## Why

A URL que o Next.js usa para repassar `/api-proxy/*` ao backend (`BACKEND_INTERNAL_URL`) é
resolvida dentro de `rewrites()` em `next.config.js` **no momento do `next build`** (modo
`output: 'standalone'`) e fica congelada em `.next/routes-manifest.json` — o `server.js` gerado não
reavalia `next.config.js` a cada request, então definir essa variável só em runtime no container não
tem efeito. `deploy/build-and-push.ps1` builda a imagem de produção do frontend via
`docker compose build frontend`, que herda o build arg `BACKEND_INTERNAL_URL: http://backend:8000`
do `docker-compose.yml` da raiz — um hostname que só existe dentro da rede Docker de desenvolvimento
local (paridade de um único host) e não resolve para nada fora dela. Com a mudança para duas EC2s
(`add-two-ec2-deploy-topology`), a imagem de produção do frontend precisa ser buildada apontando
para o endereço real do backend na VPC, não para o hostname do Compose local.

## What Changes

- `deploy/build-and-push.ps1` builda a imagem do frontend com `docker build` direto (em vez de
  `docker compose build frontend`), passando `--build-arg BACKEND_INTERNAL_URL=<IP privado do
  backend>:8000` explicitamente, junto dos dois build args `NEXT_PUBLIC_SUPABASE_*` já existentes.
- Adiciona três variáveis de preenchimento no topo do script (mesmo padrão já usado para
  `$AwsAccountId`/`$AwsRegion`/etc.): `$BackendInternalUrl`, `$NextPublicSupabaseUrl`,
  `$NextPublicSupabaseAnonKey`.
- **BREAKING** (só para quem já usa `build-and-push.ps1`): o build do frontend deixa de reaproveitar
  os build args do `docker-compose.yml` raiz — os valores de produção passam a vir só das novas
  variáveis do script, que precisam ser preenchidas antes do primeiro uso pós-mudança.
- Nenhuma mudança em `frontend/next.config.js` ou `frontend.Dockerfile` — o mecanismo de leitura do
  build arg já está correto; só o *valor* usado no build de produção estava errado.

## Capabilities

### New Capabilities
- `frontend-production-build-config`: define como os build args de produção da imagem do frontend
  (em especial `BACKEND_INTERNAL_URL`, mas também os `NEXT_PUBLIC_SUPABASE_*`) são resolvidos e
  passados pelo pipeline de build/publish, sem depender dos valores de paridade local do
  `docker-compose.yml` da raiz.

### Modified Capabilities
(nenhuma)

## Impact

- Código afetado: `deploy/build-and-push.ps1` (único arquivo alterado).
- Depende de `add-two-ec2-deploy-topology` já estar implementada/aprovada — o valor real do IP
  privado do backend só existe a partir daquela change (EC2 do backend provisionada).
- Nenhum código de aplicação (`backend/app/**`, `frontend/**`) é alterado por esta change.
