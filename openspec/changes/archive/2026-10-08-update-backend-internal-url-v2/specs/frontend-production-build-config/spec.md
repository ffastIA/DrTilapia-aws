## ADDED Requirements

### Requirement: O endereço do backend gravado na imagem do frontend aponta para um backend em execução
A imagem de produção do frontend SHALL ser construída com `BACKEND_INTERNAL_URL` igual ao endereço
privado (`http://<ip-privado>:8000`) de uma instância de backend **em execução** e alcançável a partir da
EC2 do frontend (o Security Group do backend permite a porta 8000 vinda do Security Group do frontend).
O valor SHALL estar declarado em `deploy/build-and-push.ps1`. Quando a instância de backend for
substituída ou seu IP privado mudar, o frontend SHALL ser reconstruído e republicado com o novo endereço
antes de o novo backend receber tráfego.

#### Scenario: A imagem publicada aponta para o backend atual
- **WHEN** `deploy/build-and-push.ps1` publica a imagem do frontend no ECR
- **THEN** o destino do rewrite de `/api-proxy/*` na imagem é `http://10.1.2.22:8000`, o IP privado da instância `tilapia-backend-v2`

#### Scenario: Instância de backend antiga não é mais referenciada
- **WHEN** a instância `tilapia-backend` (`10.1.20.128`) está parada ou foi removida
- **THEN** nenhum arquivo de build em `deploy/` referencia `10.1.20.128`

### Requirement: O deploy do frontend é verificado pelo caminho completo até o backend
Depois de publicar uma imagem do frontend e recriar o container, a verificação do deploy SHALL incluir
uma requisição a `/api-proxy/health` pelo domínio do CloudFront, e SHALL considerar o deploy bem-sucedido
somente se a resposta for `200` com `{"status":"ok"}` em poucos segundos. Verificar apenas as páginas do
frontend (por exemplo `/` ou `/auth/login`) SHALL NOT bastar.

#### Scenario: Backend alcançável
- **WHEN** `GET https://<dominio-cloudfront>/api-proxy/health` é executado após o deploy
- **THEN** a resposta é HTTP 200 com corpo `{"status":"ok"}` em poucos segundos

#### Scenario: Endereço do backend gravado está errado
- **WHEN** a imagem do frontend aponta para um backend parado ou inexistente
- **THEN** `GET /api-proxy/health` não responde dentro do tempo e o CloudFront devolve 504 após o `OriginReadTimeout`, enquanto `/` e `/auth/login` seguem respondendo 200 — e o deploy é tratado como falho
