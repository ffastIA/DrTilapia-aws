## Why

Em produção (EC2 privada) os segredos do backend vêm de um arquivo `deploy/backend/.env` em disco. O objetivo é lê-los do AWS Secrets Manager, mantendo o `backend/.env` no desenvolvimento local. A proposta inicial decidia o ambiente antes de ler o `.env`, o que quebra o desenvolvimento, e engolia erros de acesso ao secret.

## What Changes

- `backend/app/database.py`: carrega o `.env` primeiro (sem sobrescrever variáveis exportadas) e, se `ENVIRONMENT != development`, carrega o secret do AWS Secrets Manager. Os valores do secret prevalecem sobre o ambiente.
- Em produção, qualquer falha ao ler o secret aborta a inicialização com mensagem clara (secret, região, causa), sem valores.
- `boto3` passa a ser dependência (`requirements.txt`), importado só quando necessário.
- `deploy/docker-compose.backend.yml` repassa `SECRET_ID` e `AWS_REGION` ao container.
- Exemplos de configuração e a documentação de deploy passam a descrever secret, role IAM e IMDSv2 com hop limit 2.
- `backend/.env` local passa a definir `ENVIRONMENT=development` (o `.env.example` já definia).

## Capabilities

### New Capabilities
- `backend-secrets-source`: origem dos segredos do backend por ambiente (`.env` em desenvolvimento, Secrets Manager em produção).

### Modified Capabilities

## Impact

- Código: `backend/app/database.py`; testes em `backend/tests/test_database_secrets.py`.
- Dependência nova: `boto3`.
- Infra (fora do código): secret no Secrets Manager, role IAM da EC2 com `secretsmanager:GetSecretValue`, `HttpPutResponseHopLimit=2`, rota ao Secrets Manager.
- **Ação operacional:** remover as chaves sensíveis do `deploy/backend/.env` da EC2 depois de validar.
