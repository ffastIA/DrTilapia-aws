## 1. Rate limiting no login

- [ ] 1.1 Adicionar `slowapi` a `backend/requirements.txt`.
- [ ] 1.2 Configurar `Limiter` (chave = IP do cliente, respeitando `X-Forwarded-For`) e registrar o exception handler de `RateLimitExceeded` em `main.py`.
- [ ] 1.3 Aplicar o limite em `POST /auth/login` (ex.: 5 tentativas/minuto por IP) e, se aplicável, em `POST /auth/forgot-password`.
- [ ] 1.4 Tornar o limite configurável via variável de ambiente, com um default documentado em `backend/.env.example`.

## 2. Gate de documentação da API

- [ ] 2.1 Ler `ENVIRONMENT` (já usado no `.env` raiz) na construção do `app = FastAPI(...)`, passando `docs_url=None, redoc_url=None, openapi_url=None` quando `ENVIRONMENT != "development"`.
- [ ] 2.2 Documentar a variável e o comportamento padrão (docs desabilitadas) em `backend/.env.example`.

## 3. Verificação

- [ ] 3.1 Testar N+1 tentativas de login rápidas do mesmo IP → a partir da tentativa N+1, resposta `429`.
- [ ] 3.2 Testar login legítimo dentro do limite → comportamento inalterado.
- [ ] 3.3 Com `ENVIRONMENT` não definido/diferente de `development`: `GET /docs`, `/redoc`, `/openapi.json` → `404`.
- [ ] 3.4 Com `ENVIRONMENT=development`: os três endpoints continuam acessíveis (sem regressão para o fluxo de desenvolvimento local).
