## Why

O deploy de produção documentado hoje (`deploy/docker-compose.prod.yml`, `deploy/ec2-bootstrap.sh`,
`deploy/README.md`) assume uma única EC2 Ubuntu rodando os containers `backend` e `frontend` juntos,
com o CloudFront apontando direto para a porta 3000 do Next.js. A arquitetura alvo real mudou para
duas EC2s: uma pública ("Frontend EC2") rodando Nginx na porta 80 na frente do container Next.js
(porta 3000), e uma privada, sem IP público ("Backend EC2", ex. `10.1.20.128`), rodando só o
container FastAPI (porta 8000), alcançável apenas pela rede privada da VPC. Como hoje o backend é
publicado só em `127.0.0.1:8000:8000` (loopback) e o compose de produção mistura os dois serviços
numa única rede Docker de um único host, esse deploy quebraria por completo se aplicado como está
contra a nova topologia: o backend ficaria inacessível a partir da EC2 do frontend, e não existe
nenhum Nginx no repositório para a nova camada exigida na frente do Next.js.

## What Changes

- Dividir `deploy/docker-compose.prod.yml` em dois arquivos, um por papel/host:
  - `deploy/docker-compose.frontend.yml`: serviços `nginx` (imagem `nginx:alpine`, porta pública
    `80:80`) e `frontend` (imagem do ECR, sem porta publicada ao host — só acessível pelo Nginx via
    rede interna do Compose).
  - `deploy/docker-compose.backend.yml`: só o serviço `backend`, publicado em `0.0.0.0:8000:8000`
    (**BREAKING** em relação ao binding atual `127.0.0.1:8000:8000` — a proteção deixa de ser o
    loopback e passa a ser o Security Group da EC2 do backend).
- Criar `deploy/nginx/nginx.conf`: reverse proxy `listen 80` → `proxy_pass http://frontend:3000`,
  com `client_max_body_size` e timeouts dimensionados para os limites de upload já existentes no
  backend (vídeo até 200MB), e `X-Forwarded-Proto` fixado como `https` (a conexão CloudFront→Nginx é
  sempre HTTP; o valor real do protocolo do viewer não chega até aqui por outro caminho).
- Dividir `deploy/ec2-bootstrap.sh` em `deploy/ec2-bootstrap-frontend.sh` e
  `deploy/ec2-bootstrap-backend.sh`, cada um subindo só o compose e o healthcheck do seu papel.
- Reescrever `deploy/README.md` para o provisionamento das duas EC2s: subnet pública (frontend) e
  subnet privada com NAT Gateway (backend — necessário tanto para o backend alcançar
  Supabase/OpenAI quanto para o `docker pull` do ECR a partir da subnet privada), Security Group do
  backend liberando a porta 8000 só para o Security Group da EC2 do frontend, e o origin do
  CloudFront migrando da porta 3000 para a porta 80 (Nginx).
- `docker-compose.yml` da raiz (paridade local) e `deploy/.env.prod.example` não são alterados por
  esta change.

## Capabilities

### New Capabilities
- `deploy-topology`: define como o backend e o frontend são publicados, isolados e expostos em
  produção (topologia de containers/portas por EC2, reverse proxy Nginx, e as regras de rede —
  Security Groups, NAT Gateway, origin do CloudFront — que sustentam essa topologia).

### Modified Capabilities
(nenhuma — não há spec existente em `openspec/specs/` sobre topologia de deploy; todos os specs
atuais cobrem comportamento de aplicação, não infraestrutura de deploy)

## Impact

- Código afetado: `deploy/docker-compose.prod.yml` (removido/substituído),
  `deploy/docker-compose.frontend.yml` (novo), `deploy/docker-compose.backend.yml` (novo),
  `deploy/nginx/nginx.conf` (novo), `deploy/ec2-bootstrap.sh` (removido/substituído),
  `deploy/ec2-bootstrap-frontend.sh` (novo), `deploy/ec2-bootstrap-backend.sh` (novo),
  `deploy/README.md` (reescrito).
- Nenhum código de aplicação (`backend/app/**`, `frontend/**`) é alterado por esta change.
- Infraestrutura AWS necessária fora do repositório (não versionável aqui, só documentada no
  README): segunda EC2 numa subnet privada, NAT Gateway, ajuste do Security Group do backend e do
  origin do CloudFront.
- Depende desta change: `fix-frontend-backend-buildtime-url` (referencia o IP privado do backend
  definido aqui para buildar a imagem de produção do frontend).
