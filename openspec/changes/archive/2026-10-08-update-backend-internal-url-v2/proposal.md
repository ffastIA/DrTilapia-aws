## Why

Depois do deploy das imagens arm64, o login no CloudFront passou a falhar com **504 Gateway Timeout**.
As páginas do frontend respondem normalmente (`/` e `/auth/login`, HTTP 200 em menos de 1 s), mas
qualquer chamada ao backend pelo proxy do Next.js (`/api-proxy/*`) fica pendurada até o CloudFront
desistir (`OriginReadTimeout` de 55 s).

A causa é o endereço do backend gravado na imagem do frontend. `BACKEND_INTERNAL_URL` é resolvido em
build-time (`next build` congela o destino do rewrite em `.next/routes-manifest.json` — ver
`frontend.Dockerfile` e a change arquivada `fix-frontend-backend-buildtime-url`), e
`deploy/build-and-push.ps1` ainda usa `http://10.1.20.128:8000`, o IP privado da instância
`tilapia-backend` (`i-0d2ef8379a4c4c0cd`), que está **parada**. O backend em uso agora é a instância
`tilapia-backend-v2` (`i-0eeca103e61379d4b`, criada em 2026-10-01), em outra sub-rede, com IP privado
`10.1.2.22`. O Security Group do backend (`sg-0857384097046e629`) já libera a porta 8000 para o Security
Group do frontend; só o endereço gravado na imagem está desatualizado.

## What Changes

- `deploy/build-and-push.ps1`: `$BackendInternalUrl` passa de `http://10.1.20.128:8000` para
  `http://10.1.2.22:8000`.
- Reconstruir a imagem do frontend (arm64) e publicá-la no ECR com o novo endereço; recriar o container do
  frontend na EC2 `tilapia-frontend`.
- Documentar, na spec `frontend-production-build-config`, que o endereço gravado na imagem deve ser o de
  uma instância de backend em execução e como verificar isso após cada deploy.
- Nenhuma mudança de código do frontend ou do backend.

## Capabilities

### New Capabilities
- `frontend-production-build-config`: como a imagem de produção do frontend é construída e qual endereço
  de backend ela carrega (a spec correspondente da change arquivada `fix-frontend-backend-buildtime-url`
  nunca foi sincronizada com `openspec/specs`, então os requisitos novos entram como ADDED).

### Modified Capabilities
<!-- nenhuma -->

## Impact

- `deploy/build-and-push.ps1` (uma linha).
- Imagem `drtilapia-aws-frontend:latest` no ECR (nova versão arm64) e o container do frontend na EC2.
- Risco operacional recorrente: o IP privado de uma EC2 muda quando a instância é recriada, e o frontend
  precisa ser reconstruído a cada vez (ver design).
