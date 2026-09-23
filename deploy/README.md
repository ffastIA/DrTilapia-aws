# Deploy — EC2 + CloudFront

Alvo de deploy: uma instância EC2 Ubuntu rodando os dois containers via
Docker Compose, com o CloudFront apontando pra ela como origin. As imagens
são construídas na máquina de desenvolvimento (Windows) e publicadas num
ECR — a EC2 nunca builda a partir do código-fonte, só puxa imagem pronta.

## Passos únicos (uma vez, antes do primeiro deploy)

1. **Criar os 2 repositórios ECR** (console ou `aws ecr create-repository
   --repository-name <nome>` — um para o backend, um para o frontend).
2. **Criar a instância EC2** (Ubuntu) com:
   - **Instance profile IAM** anexado, com uma policy que só permita leitura
     nesses 2 repositórios ECR (`ecr:GetDownloadUrlForLayer`,
     `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`, mais
     `ecr:GetAuthorizationToken` — este último exige `Resource: "*"`, os
     demais podem ser restritos aos ARNs dos 2 repositórios). Não usar
     chave de acesso estática (`AWS_ACCESS_KEY_ID`) em lugar nenhum.
   - **IMDSv2 obrigatório**: `aws ec2 modify-instance-metadata-options
     --instance-id <id> --http-tokens required --http-endpoint enabled`
     (ou já marcar isso na criação). Confirmar depois com
     `aws ec2 describe-instances --instance-ids <id> --query
     'Reservations[].Instances[].MetadataOptions.HttpTokens'` → deve
     retornar `"required"`.
   - **Security Group**: porta 3000 liberada **só** para o prefix list
     gerenciado `com.amazonaws.global.cloudfront.origin-facing` (não
     `0.0.0.0/0` — senão qualquer um que descobrir o IP da instância acessa
     direto, pulando o CloudFront). Porta 22 (SSH) restrita ao seu IP.
3. **Criar a distribuição CloudFront** apontando pra essa EC2 (porta 3000,
   `Origin Protocol Policy = HTTP Only`), `Viewer Protocol Policy = Redirect
   HTTP to HTTPS`, cache policy `CachingDisabled` + origin request policy
   que encaminhe cookies (o app é dinâmico e autenticado). Anote o domínio
   `*.cloudfront.net` gerado.
4. **Copiar este diretório `deploy/` pra EC2** (scp/rsync — não precisa do
   resto do repositório):
   ```
   scp -r deploy/ ubuntu@<ip-da-ec2>:~/deploy/
   ```
5. **Criar `deploy/.env` na EC2** a partir de `deploy/.env.prod.example`,
   preenchido com os valores reais do ECR e a tag publicada pelo
   `build-and-push.ps1` mais recente.
6. **Criar `deploy/backend/.env` na EC2** (pasta `backend/` dentro de
   `deploy/`, ao lado do `docker-compose.prod.yml`) a partir de
   `backend/.env.example` do repositório — **não copiar o `.env` de
   desenvolvimento do Windows**, que tem `ENVIRONMENT=development`,
   `ALLOWED_ORIGINS`/`FRONTEND_URL` apontando pra `localhost` e paths de CA
   bundle do Windows que não existem nem fazem sentido na EC2. Na EC2:
   - **Sem** `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` (deixar vazio/ausente — a
     EC2 não está atrás do proxy corporativo, a verificação TLS padrão via
     certifi funciona direto).
   - `ALLOWED_ORIGINS` e `FRONTEND_URL` com o domínio `*.cloudfront.net` do
     passo 3, com `https://`.
   - Cadastrar esse mesmo domínio como Redirect URL no Supabase Auth
     (Dashboard → Authentication → URL Configuration).
7. **Rodar o bootstrap**:
   ```
   ssh ubuntu@<ip-da-ec2>
   cd ~/deploy
   chmod +x ec2-bootstrap.sh
   sudo ./ec2-bootstrap.sh
   ```

## A cada novo deploy (depois do primeiro)

1. Na máquina Windows: `.\deploy\build-and-push.ps1` (builda, tageia com o
   SHA do commit atual, publica no ECR).
2. Atualizar `IMAGE_TAG` no `deploy/.env` da EC2 com a nova tag.
3. Na EC2:
   ```
   cd ~/deploy
   docker compose -f docker-compose.prod.yml --env-file .env pull
   docker compose -f docker-compose.prod.yml --env-file .env up -d
   ```

## O que este diretório NÃO resolve (decisão consciente, documentada aqui)

- **CI/CD automatizado**: hoje o build ainda é manual, disparado por quem
  rodar `build-and-push.ps1`. Nenhum GitHub Actions/CodeBuild foi criado —
  isso é um passo futuro, não coberto por este `deploy/`.
- **Rotação de segredos**: `backend/.env` da EC2 precisa ter permissão
  `600` e dono correto (`chmod 600 backend/.env`) — o bootstrap não faz
  isso automaticamente porque a policy exata de quem acessa a instância
  varia por equipe.
- **Domínio próprio + ACM**: este setup usa o domínio padrão
  `*.cloudfront.net`. Se depois quiser um domínio próprio, é preciso um
  certificado ACM em `us-east-1` anexado à distribuição e um registro
  DNS — não coberto aqui.
