# Deploy — 2 EC2s (Nginx/Next.js público + FastAPI privado) + CloudFront

Alvo de deploy: **duas instâncias EC2 Ubuntu**, não mais uma só.

```
Usuário → HTTPS → CloudFront
   → HTTP porta 80 → Nginx (EC2 Frontend, pública, subnet pública)
   → HTTP porta 3000 → Next.js container
   → HTTP porta 8000 → FastAPI container (EC2 Backend, privada, subnet privada)
   → HTTPS (via NAT Gateway) → Supabase / OpenAI
```

- **EC2 Frontend** (subnet pública, com IP público): roda `nginx:alpine` (porta 80, recebe o
  CloudFront) na frente do container `frontend` (porta 3000, não publicada ao host — só o Nginx a
  alcança pela rede interna do Compose).
- **EC2 Backend** (subnet privada, **sem** IP público): roda só o container `backend` (porta 8000),
  alcançável apenas pela EC2 do frontend através da rede da VPC — nunca pela internet pública.

As imagens são construídas na máquina de desenvolvimento (Windows) e publicadas num ECR — nenhuma
das duas EC2s builda a partir do código-fonte, só puxa imagem pronta. O `BACKEND_INTERNAL_URL`
usado pelo Next.js para alcançar o backend é resolvido em **build-time** (não runtime) — ver
` e a change `fix-frontend-backend-buildtime-url`.

## Passos únicos (uma vez, antes do primeiro deploy)

1. **Criar os 2 repositórios ECR** (console ou `aws ecr create-repository
   --repository-name <nome>` — um para o backend, um para o frontend).
2. **Provisionar a rede**:
   - **Subnet pública** para a EC2 do frontend, com rota para um Internet Gateway (IGW).
   - **Subnet privada** para a EC2 do backend, com rota de saída via **NAT Gateway** — necessária
     tanto para o backend alcançar Supabase/OpenAI (`HTTPS` de saída) quanto para o `docker pull`
     das imagens do ECR a partir de uma subnet sem IP público.
3. **Criar a EC2 do Frontend** (Ubuntu, subnet pública, com IP público) com:
   - **Instance profile IAM** anexado, com uma policy que só permita leitura no repositório ECR do
     **frontend** (`ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`,
     `ecr:BatchCheckLayerAvailability`, mais `ecr:GetAuthorizationToken` — este último exige
     `Resource: "*"`, os demais podem ser restritos ao ARN do repositório). Não usar chave de
     acesso estática (`AWS_ACCESS_KEY_ID`) em lugar nenhum.
   - **IMDSv2 obrigatório**: `aws ec2 modify-instance-metadata-options --instance-id <id>
     --http-tokens required --http-endpoint enabled` (ou já marcar isso na criação). Confirmar
     depois com `aws ec2 describe-instances --instance-ids <id> --query
     'Reservations[].Instances[].MetadataOptions.HttpTokens'` → deve retornar `"required"`.
   - **Security Group do frontend**: porta 80 liberada **só** para o prefix list gerenciado
     `com.amazonaws.global.cloudfront.origin-facing` (não `0.0.0.0/0` — senão qualquer um que
     descobrir o IP da instância acessa direto, pulando o CloudFront). Porta 22 (SSH) já é coberta
     por um Security Group existente, restrito por IP de origem — nada a fazer aqui.
4. **Criar a EC2 do Backend** (Ubuntu, subnet privada, **sem** IP público) com:
   - **Instance profile IAM** próprio, com a mesma política de leitura do ECR (desta vez só para o
     repositório do **backend**). Idem: sem chave estática.
   - **IMDSv2 obrigatório**, mesma verificação do passo 3.
   - **Security Group do backend**: porta 8000 liberada **só** para o Security Group da EC2 do
     Frontend (regra referenciando o Security Group como origem, não um CIDR — nunca `0.0.0.0/0`
     nem uma faixa ampla). Porta 22 também já coberta pelo Security Group existente mencionado
     acima.
5. **Criar a distribuição CloudFront** apontando pra EC2 do **Frontend** (porta **80**, não 3000 —
   é o Nginx que recebe o tráfego agora), `Origin Protocol Policy = HTTP Only`,
   `Viewer Protocol Policy = Redirect HTTP to HTTPS`, cache policy `CachingDisabled` + origin
   request policy que encaminhe cookies (o app é dinâmico e autenticado). Anote o domínio
   `*.cloudfront.net` gerado.
6. **Copiar `deploy/` pra cada EC2** (scp/rsync — não precisa do resto do repositório; a EC2 do
   frontend também precisa de `deploy/nginx/nginx.conf`, incluído automaticamente se copiar o
   diretório inteiro):
   ```
   scp -r deploy/ ubuntu@<ip-publico-ec2-frontend>:~/deploy/
   scp -r deploy/ ubuntu@<ip-privado-ec2-backend>:~/deploy/   # via bastion/VPN/SSM, já que é privada
   ```
7. **Criar `deploy/.env` em cada EC2** a partir de `deploy/.env.prod.example`, preenchido com os
   valores reais do ECR (cada uma só precisa do repositório do seu próprio papel) e a `IMAGE_TAG`
   publicada pelo `build-and-push.ps1` mais recente.
8. **Criar `deploy/backend/.env` só na EC2 do Backend** (pasta `backend/` dentro de `deploy/`, ao
   lado do `docker-compose.backend.yml`) a partir de `backend/.env.example` do repositório — **não
   copiar o `.env` de desenvolvimento do Windows**, que tem `ENVIRONMENT=development`,
   `ALLOWED_ORIGINS`/`FRONTEND_URL` apontando pra `localhost` e paths de CA bundle do Windows que
   não existem nem fazem sentido na EC2. Nesse arquivo:
   - **Sem** `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` (deixar vazio/ausente — a EC2 não está atrás do
     proxy corporativo, a verificação TLS padrão via certifi funciona direto pela rota do NAT
     Gateway).
   - `ALLOWED_ORIGINS` e `FRONTEND_URL` com o domínio `*.cloudfront.net` do passo 5, com `https://`.
   - Cadastrar esse mesmo domínio como Redirect URL no Supabase Auth (Dashboard → Authentication →
     URL Configuration).
9. **Rodar o bootstrap em cada EC2**:
   ```
   # EC2 do Frontend
   ssh ubuntu@<ip-publico-ec2-frontend>
   cd ~/deploy
   chmod +x ec2-bootstrap-frontend.sh
   sudo ./ec2-bootstrap-frontend.sh

   # EC2 do Backend (via bastion/VPN/SSM, já que não tem IP público)
   ssh ubuntu@<ip-privado-ec2-backend>
   cd ~/deploy
   chmod +x ec2-bootstrap-backend.sh
   sudo ./ec2-bootstrap-backend.sh
   ```
   Não há ordem obrigatória entre as duas — cada bootstrap só depende dos arquivos do seu próprio
   diretório — mas validar o backend primeiro (`curl http://localhost:8000/health` na própria EC2
   do backend) facilita isolar problemas antes de testar a cadeia completa via CloudFront.

## A cada novo deploy (depois do primeiro)

1. Na máquina Windows: `.\deploy\build-and-push.ps1` (builda os dois, tageia com o SHA do commit
   atual, publica no ECR — o build do frontend usa o IP privado real do backend como
   `BACKEND_INTERNAL_URL`, não o hostname de desenvolvimento; ver
   `fix-frontend-backend-buildtime-url`).
2. Atualizar `IMAGE_TAG` no `deploy/.env` de **cada** EC2 com a nova tag.
3. Em cada EC2 (independentes uma da outra):
   ```
   cd ~/deploy
   docker compose -f docker-compose.frontend.yml --env-file .env pull   # EC2 do frontend
   docker compose -f docker-compose.frontend.yml --env-file .env up -d

   docker compose -f docker-compose.backend.yml --env-file .env pull    # EC2 do backend
   docker compose -f docker-compose.backend.yml --env-file .env up -d
   ```

## O que este diretório NÃO resolve (decisão consciente, documentada aqui)

- **CI/CD automatizado**: hoje o build ainda é manual, disparado por quem rodar
  `build-and-push.ps1`. Nenhum GitHub Actions/CodeBuild foi criado — isso é um passo futuro, não
  coberto por este `deploy/`.
- **Rotação de segredos**: `backend/.env` da EC2 do backend precisa ter permissão `600` e dono
  correto (`chmod 600 backend/.env`) — o bootstrap não faz isso automaticamente porque a policy
  exata de quem acessa a instância varia por equipe.
- **Domínio próprio + ACM**: este setup usa o domínio padrão `*.cloudfront.net`. Se depois quiser um
  domínio próprio, é preciso um certificado ACM em `us-east-1` anexado à distribuição e um registro
  DNS — não coberto aqui.
- **IP privado fixo do backend**: `BACKEND_INTERNAL_URL` é embutido na imagem do frontend com o IP
  privado real da EC2 do backend (decisão deliberada — ver `fix-frontend-backend-buildtime-url`).
  Isso funciona enquanto a mesma instância existir (o IP privado primário de uma EC2 persiste entre
  stop/start), mas **se a EC2 do backend for recriada** (terminada e substituída), seu IP privado
  muda e a imagem do frontend precisa ser rebuildada e republicada com o novo valor — não há DNS
  privado (Route 53) nesta topologia para absorver essa mudança automaticamente.
