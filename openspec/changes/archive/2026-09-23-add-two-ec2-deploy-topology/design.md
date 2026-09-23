## Context

Hoje o repositório documenta e implementa (`deploy/docker-compose.prod.yml`,
`deploy/ec2-bootstrap.sh`, `deploy/README.md`) uma única EC2 Ubuntu rodando `backend` e `frontend`
juntos via Docker Compose, numa rede bridge compartilhada `dr_tilapia_net`. O backend é publicado só
em `127.0.0.1:8000:8000` (loopback) porque o frontend o alcança pelo DNS interno do Compose
(`http://backend:8000`) no mesmo host. O CloudFront aponta direto para a porta 3000 da EC2.

A arquitetura alvo (fornecida pelo usuário) é:

```
Usuário → HTTPS → CloudFront (a criar)
   → HTTP porta 80 → Nginx (EC2 Frontend, pública — ex. 54.20.140.148)
   → HTTP porta 3000 → Next.js container
   → HTTP porta 8000 (10.1.20.128) → FastAPI container (EC2 Backend, privada)
   → HTTPS (via NAT Gateway) → Supabase
```

Uma auditoria do repositório (busca pelos IPs, "NAT Gateway", "VPC", `nginx.conf`) não encontrou
nenhum artefato existente para essa topologia — tudo precisa ser criado ou adaptado do modelo de
EC2 única atual.

## Goals / Non-Goals

**Goals:**
- Tornar o backend alcançável pela EC2 do frontend através da rede privada da VPC, sem expô-lo à
  internet pública.
- Introduzir o Nginx como reverse proxy na frente do Next.js, absorvendo o tráfego do CloudFront na
  porta 80 (HTTP) e repassando para o container Next.js na porta 3000.
- Manter o padrão já usado no projeto de "a EC2 só puxa imagem pronta do ECR, nunca builda a partir
  do código-fonte" — o Nginx entra como imagem oficial (`nginx:alpine`) com config montada, não como
  build próprio.
- Documentar em `deploy/README.md` os pré-requisitos de rede (subnets, Security Groups, NAT Gateway)
  necessários para essa topologia funcionar, já que não são versionáveis como código.

**Non-Goals:**
- Automatizar o provisionamento da infraestrutura AWS (Terraform/CloudFormation) — fora de escopo,
  como já era antes desta change (`deploy/` documenta passos manuais/CLI, não IaC).
- Resolver o timeout de origin do CloudFront para respostas longas (análise de imagem/OCR) — risco
  pré-existente à topologia de EC2 única, não introduzido por esta change.
- Alterar como o frontend resolve o endereço do backend em build-time (`BACKEND_INTERNAL_URL`) —
  coberto pela change dependente `fix-frontend-backend-buildtime-url`.
- Adicionar autenticação de rede (mTLS, header compartilhado) entre Nginx/Next.js e o backend — a
  proteção do backend continua sendo (a) o Security Group restringindo a porta 8000 só à EC2 do
  frontend e (b) a validação de token por request já existente (`get_current_user` chamando a Auth
  API do Supabase).

## Decisions

### D1 — Backend publicado em `0.0.0.0:8000:8000`, protegido por Security Group (não mais por loopback)
O binding atual (`127.0.0.1:8000:8000`) foi escolhido deliberadamente para impedir acesso externo
num host que também expõe o frontend publicamente. Com o backend isolado numa EC2 própria sem IP
público, a proteção equivalente passa a ser o Security Group: porta 8000 liberada **só** para o
Security Group da EC2 do frontend (regra SG-para-SG, nunca CIDR/`0.0.0.0/0`). Alternativa
descartada: manter loopback e usar um túnel/SSH port-forward do frontend para o backend — adiciona
complexidade operacional sem ganho de segurança sobre a regra de Security Group.

### D2 — Nginx como container (`nginx:alpine` + config montada), não instalado via `apt` na EC2
Mantém consistência com o resto do projeto, que só faz `docker pull` de imagens prontas na EC2 e não
builda nada localmente nela. Um `nginx:alpine` oficial com `deploy/nginx/nginx.conf` montado por
bind mount cobre o caso de uso sem precisar de build próprio nem de gestão de pacote do SO.
Alternativa descartada: instalar Nginx via `apt` no `ec2-bootstrap-frontend.sh` — funcionaria, mas
introduz um segundo mecanismo de gestão de versão/atualização (pacote do SO) ao lado do padrão
Docker já estabelecido para tudo o resto.

### D3 — `docker-compose.prod.yml` dividido em dois arquivos por papel, não um único arquivo com profiles
Compose `profiles` poderiam simular "rodar só backend" ou "só frontend" a partir de um arquivo
único, mas isso manteria os dois serviços acoplados na mesma definição de rede/depends_on, que não
faz sentido entre hosts diferentes (o Compose não tem como avaliar `depends_on: condition:
service_healthy` de um serviço rodando numa EC2 diferente). Dois arquivos simples, cada um só com o
que roda naquele host, é mais direto de auditar e copiar (`scp`) para a EC2 correspondente.

### D4 — `X-Forwarded-Proto: https` fixado (hardcoded) no Nginx, não derivado de `$scheme`
A conexão CloudFront→Nginx é sempre HTTP (só o trecho viewer↔CloudFront é HTTPS — "Origin Protocol
Policy = HTTP Only", já documentado no `deploy/README.md` atual), então `$scheme` no Nginx sempre
valeria `http`, mascarando o protocolo real usado pelo usuário. Fixar `https` é seguro neste caso
porque o Security Group da EC2 do frontend só aceitará tráfego na porta 80 vindo do prefix list
gerenciado do CloudFront (`com.amazonaws.global.cloudfront.origin-facing`) — não existe caminho de
acesso direto por HTTP puro que tornaria esse valor incorreto. Alternativa descartada: configurar um
Origin Request Policy / Lambda@Edge no CloudFront para injetar o header — mais infraestrutura para o
mesmo resultado, já que o valor é estático de qualquer forma nesta topologia.

### D5 — `client_max_body_size` e timeouts do Nginx dimensionados pelos limites já existentes no backend
`backend/app/utils/upload_validation.py` já define `MAX_UPLOAD_SIZE_VIDEO_MB=200` (o maior limite
entre os tipos aceitos). O default do Nginx (`client_max_body_size 1m`) rejeitaria esses uploads
antes de chegar ao Next.js. Valor escolhido: `client_max_body_size 220M` (margem sobre 200MB).
`proxy_read_timeout`/`proxy_send_timeout` alongados (300s) para cobrir upload grande + processamento
(remoção de fundo via rembg) sem o Nginx cortar a conexão antes do backend responder.

## Risks / Trade-offs

- **[Risco] Backend acessível por qualquer host dentro do Security Group do frontend, não só pelo
  Nginx/Next.js especificamente.** → Mitigação: regra de Security Group aponta para o SG da EC2 do
  frontend como um todo (não há como restringir por processo dentro do host); aceitável porque essa
  EC2 já é de confiança na topologia (única expost ao público) e o backend valida token por request
  independentemente da origem da chamada.
- **[Risco] Nginx vira um novo ponto de falha entre CloudFront e o Next.js.** → Mitigação:
  `depends_on: frontend: condition: service_healthy` no compose do frontend garante que o Nginx só
  sobe depois do Next.js responder saudável; `restart: unless-stopped` em ambos os serviços.
- **[Trade-off] `client_max_body_size 220M` e timeouts de 300s no Nginx abrem uma janela maior para
  requests lentos/grandes segurarem uma conexão worker do Nginx.** → Aceito: o volume de uploads
  (imagens de biometria de peixe, vídeos, PDFs) é baixo e autenticado; não há endpoint público
  anônimo que aceite upload.
- **[Risco, fora do controle desta change] Timeout de origin do CloudFront (30-60s) pode cortar
  respostas de análise de imagem/OCR mais lentas antes mesmo de chegar no Nginx.** → Não mitigado
  aqui (ver Non-Goals); recomendado validar com teste real depois do deploy.

## Migration Plan

1. Criar os novos arquivos (`docker-compose.frontend.yml`, `docker-compose.backend.yml`,
   `nginx/nginx.conf`, os dois scripts de bootstrap) **sem remover ainda**
   `deploy/docker-compose.prod.yml`/`deploy/ec2-bootstrap.sh` do histórico do Git (a remoção final é
   uma tarefa do `tasks.md`, mas pode ficar para o fim da implementação, depois de validado).
2. Provisionar a EC2 privada do backend (fora do repositório — console/CLI AWS) numa subnet privada
   com rota de saída via NAT Gateway; criar/ajustar o Security Group do backend.
3. Publicar as imagens no ECR como já acontece (`deploy/build-and-push.ps1`, sem mudança nesta
   change).
4. Subir `docker-compose.backend.yml` na EC2 privada primeiro; validar
   `curl http://10.1.20.128:8000/health` **a partir de dentro da VPC** (ex.: de dentro da futura EC2
   do frontend, ou de uma instância temporária na mesma subnet).
5. Subir `docker-compose.frontend.yml` (Nginx + frontend) na EC2 pública; validar
   `curl http://localhost/` respondendo via Nginx.
6. Atualizar o origin do CloudFront da porta 3000 para a porta 80 e liberar o Security Group do
   frontend para a porta 80 (prefix list do CloudFront).
7. Só depois de validado ponta a ponta, remover `deploy/docker-compose.prod.yml` e
   `deploy/ec2-bootstrap.sh` (substituídos pelos arquivos por papel).

**Rollback**: reverter o origin do CloudFront para a porta 3000 da EC2 antiga (se ainda ativa) ou
para o Nginx respondendo na 80 se o problema for só no Next.js; como os dois hosts são independentes,
qualquer um pode ser revertido/recriado sem afetar o outro.

## Open Questions

Nenhuma pendente — as duas decisões de infraestrutura relevantes (endereçamento do backend por IP
privado direto, e acesso SSH via Security Group já existente) foram fechadas com o usuário antes
desta change e são tratadas na change dependente `fix-frontend-backend-buildtime-url` e no
`deploy/README.md` respectivamente.
