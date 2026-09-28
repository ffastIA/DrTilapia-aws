## Context

`database.py` lia sempre o `.env`. O `ENVIRONMENT=development` só existe dentro do `.env`, então decidir o ambiente antes de lê-lo cai em `production` no ambiente local. O `docker-compose.backend.yml` já força `ENVIRONMENT=production` na EC2.

## Goals / Non-Goals

**Goals:**
- Desenvolvimento usa o `.env`; produção usa o Secrets Manager.
- Falha rápida e clara em produção quando o secret não é legível.

**Non-Goals:**
- Criar o secret, a role IAM ou alterar a infraestrutura AWS.
- Migrar variáveis não secretas (`FRONTEND_URL`, `ALLOWED_ORIGINS`).
- Rotação automática de segredos.

## Decisions

**Carregar o `.env` antes de decidir o ambiente.** `load_dotenv` não sobrescreve variáveis exportadas e não faz nada sem o arquivo (imagem de produção não tem `.env`). Descartado: decidir por `os.getenv` puro, que quebra o desenvolvimento.

**O secret prevalece sobre o ambiente (`os.environ[k] = v`, não `setdefault`).** Um valor antigo num `env_file` da instância não pode vencer o segredo vigente.

**Falha explícita em produção (`RuntimeError`).** Descartado: só registrar aviso, que atrasa o erro para um `ValueError` sem relação aparente.

**`boto3` com import tardio.** Evita custo de memória e dependência em desenvolvimento.

## Risks / Trade-offs

- [Desenvolvimento sem `ENVIRONMENT=development` no `.env` tenta a AWS e falha] → mensagem cita SECRET_ID e região; `.env.example` documenta a variável.
- [Container não alcança as credenciais da role (IMDSv2 hop limit 1)] → documentar `HttpPutResponseHopLimit=2`.
- [Secret sem alguma chave usada em runtime (ex.: `OPENAI_API_KEY`)] → só quebra ao usar o RAG; validar o conteúdo do secret no deploy.
