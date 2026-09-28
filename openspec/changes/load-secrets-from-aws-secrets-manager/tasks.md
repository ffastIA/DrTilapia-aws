## 1. Implementação

- [x] 1.1 Reescrever o bloco de configuração de `backend/app/database.py`: `.env` primeiro, depois Secrets Manager fora de desenvolvimento, secret prevalecendo, falha explícita
- [x] 1.2 Adicionar `boto3` a `backend/requirements.txt`
- [x] 1.3 Repassar `SECRET_ID` e `AWS_REGION` em `deploy/docker-compose.backend.yml`
- [x] 1.4 Documentar em `backend/.env.example`, `deploy/.env.prod.example` e `deploy/AWS_arquitetura_230926.md` (secret, role IAM, hop limit 2)
- [x] 1.5 Definir `ENVIRONMENT=development` no `backend/.env` local

## 2. Testes

- [x] 2.1 Criar `backend/tests/test_database_secrets.py` cobrindo os cenários da spec
- [x] 2.2 Rodar a suíte completa sem regressões
- [x] 2.3 Confirmar o import em desenvolvimento com o `.env` real e sem `boto3`

## 3. Validação em produção (fora do código)

- [ ] 3.1 Criar/conferir o secret com `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`
- [ ] 3.2 Conceder `secretsmanager:GetSecretValue` à role da EC2 e configurar `HttpPutResponseHopLimit=2`
- [ ] 3.3 Publicar nova imagem, recriar o container sem chaves sensíveis no `.env` e validar `/health` e um login
- [ ] 3.4 Remover as chaves sensíveis do `deploy/backend/.env` da EC2
