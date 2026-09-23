## 1. Compose files por papel

- [x] 1.1 Criar `deploy/docker-compose.backend.yml`: serviço `backend` (imagem
      `${ECR_REGISTRY}/${ECR_REPO_BACKEND}:${IMAGE_TAG}`, `env_file: backend/.env`, `environment:
      ENVIRONMENT`), publicado em `0.0.0.0:8000:8000` (não mais `127.0.0.1:8000:8000`),
      `restart: unless-stopped`.
- [x] 1.2 Criar `deploy/docker-compose.frontend.yml`: serviço `nginx` (imagem `nginx:alpine`, porta
      `80:80`, monta `./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro`,
      `depends_on: frontend: condition: service_healthy`) e serviço `frontend` (imagem
      `${ECR_REGISTRY}/${ECR_REPO_FRONTEND}:${IMAGE_TAG}`, sem `ports:` publicada ao host).
- [ ] 1.3 Remover `deploy/docker-compose.prod.yml` (substituído pelos dois arquivos acima) — só
      depois que 1.1/1.2 estiverem validados (ver seção 5).

## 2. Nginx

- [x] 2.1 Criar `deploy/nginx/nginx.conf`: `server { listen 80; }`, `client_max_body_size 220M;`,
      `proxy_read_timeout 300s; proxy_send_timeout 300s; proxy_connect_timeout 10s;`,
      `location / { proxy_pass http://frontend:3000; proxy_http_version 1.1; proxy_set_header Host
      $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For
      $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto https; }`.
- [x] 2.2 Comentar no próprio `nginx.conf` por que `X-Forwarded-Proto` é fixado como `https` (ver
      design.md, decisão D4), para quem ler depois não "corrigir" para `$scheme`.

## 3. Scripts de bootstrap por papel

- [x] 3.1 Criar `deploy/ec2-bootstrap-frontend.sh` a partir de `deploy/ec2-bootstrap.sh`: valida
      `.env`, `docker-compose.frontend.yml` e `nginx/nginx.conf` presentes; instala Docker; pull +
      up com `-f docker-compose.frontend.yml`; healthcheck final via `curl -s http://localhost/`.
- [x] 3.2 Criar `deploy/ec2-bootstrap-backend.sh` a partir de `deploy/ec2-bootstrap.sh`: valida
      `.env`, `docker-compose.backend.yml` e `backend/.env` presentes; instala Docker; pull + up com
      `-f docker-compose.backend.yml`; healthcheck final via `curl -s http://localhost:8000/health`.
- [ ] 3.3 Remover `deploy/ec2-bootstrap.sh` (substituído pelos dois scripts acima) — só depois que
      3.1/3.2 estiverem validados (ver seção 5).

## 4. Documentação (`deploy/README.md`)

- [x] 4.1 Reescrever a introdução: alvo passa de "uma EC2" para "duas EC2s" (frontend pública +
      backend privada), com o diagrama da nova topologia.
- [x] 4.2 Documentar o provisionamento de rede: subnet pública (frontend) e subnet privada com rota
      de saída via NAT Gateway (backend — necessário para Supabase/OpenAI e para `docker pull` do
      ECR a partir da subnet privada).
- [x] 4.3 Documentar o Security Group do backend: porta 8000 liberada só para o Security Group da
      EC2 do frontend (regra SG-para-SG, nunca CIDR/`0.0.0.0/0`); registrar que o acesso SSH às duas
      EC2s já é coberto por um Security Group existente (fora de escopo desta change).
- [x] 4.4 Atualizar o passo do CloudFront: origin na porta 80 (Nginx) em vez de 3000, mantendo
      `Origin Protocol Policy = HTTP Only` e `Viewer Protocol Policy = Redirect HTTP to HTTPS`.
- [x] 4.5 Reescrever os passos de deploy (único e "a cada novo deploy") como dois fluxos paralelos,
      um por EC2, referenciando os arquivos criados nas seções 1-3.

## 5. Validação ponta a ponta

- [ ] 5.1 Subir `docker-compose.backend.yml` na EC2 privada; confirmar
      `curl http://<ip-privado-backend>:8000/health` respondendo a partir de dentro da VPC.
- [ ] 5.2 Subir `docker-compose.frontend.yml` na EC2 pública; confirmar `curl http://localhost/`
      (via Nginx) retornando a página do Next.js.
- [ ] 5.3 Testar um upload de vídeo grande (próximo de 200MB) via `/api-proxy/*` e confirmar que o
      Nginx não retorna 413 nem corta a conexão por timeout.
- [ ] 5.4 Apontar o origin do CloudFront para a porta 80 e validar o fluxo completo
      (usuário → CloudFront → Nginx → Next.js → FastAPI → Supabase) por um domínio `*.cloudfront.net`
      de teste.
- [ ] 5.5 Confirmar no Security Group do backend que só a porta 8000 vinda do Security Group do
      frontend é aceita (testar uma tentativa de conexão de fora desse SG e confirmar rejeição).
- [ ] 5.6 Remover `deploy/docker-compose.prod.yml` e `deploy/ec2-bootstrap.sh` (tarefas 1.3 e 3.3)
      só depois que 5.1-5.5 passarem.
