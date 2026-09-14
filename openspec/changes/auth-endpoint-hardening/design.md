## Context

`backend/app/main.py:80`: `app = FastAPI()` — sem argumentos, então os defaults do Starlette/FastAPI (`docs_url="/docs"`, `redoc_url="/redoc"`, `openapi_url="/openapi.json"`) ficam ativos sempre.

`backend/app/main.py:100`: `@app.post("/auth/login", response_model=LoginResponse)` — o handler delega a `auth_service.login(...)`, sem nenhum decorator/dependência de limitação de taxa antes.

Já confirmado como correto (fora de escopo): `backend/app/dependencies.py:54-69` já diferencia `AuthApiError` (→ 401, com log) de exceções genuinamente inesperadas (→ 500, com `logger.exception`).

## Goals / Non-Goals

**Goals:**
- Login e (se aplicável) esqueci-senha protegidos contra tentativas em alta velocidade.
- `/docs`/`/redoc`/`/openapi.json` não expostos por padrão fora de ambiente de desenvolvimento.

**Non-Goals:**
- Não implementar CAPTCHA ou verificação humana — rate limiting simples por IP/identificador é suficiente para este escopo.
- Não mudar a validação remota do JWT contra o Supabase (`supabase.auth.get_user`) para verificação local via JWKS — é uma otimização de performance/latência relacionada ao item H2 da auditoria (I/O bloqueante), não uma falha de segurança por si só (a validação remota já falha fechado), e fica fora do escopo desta mudança.

## Decisions

1. **Rate limiting via `slowapi`** (wrapper de `limits` para Starlette/FastAPI), por ser a biblioteca mais madura e testada para este framework, em vez de implementar um limitador in-memory manual — evita reinventar lógica de janela deslizante/token bucket.
2. **Chave de limitação**: IP do cliente como chave primária (via `get_remote_address` do `slowapi`, respeitando `X-Forwarded-For` quando atrás de um load balancer — relevante após a containerização atrás de um ALB). Combinar com o email/identificador da tentativa como chave secundária é uma melhoria possível, mas o limite por IP já cobre o cenário de força bruta em massa.
3. **Gate de docs por env**: usar uma variável já convencionada no projeto (`ENVIRONMENT`, já presente no `.env` raiz) — quando `ENVIRONMENT != "development"`, `docs_url`/`redoc_url`/`openapi_url` são passados como `None` ao construtor do `FastAPI`.

## Risks / Trade-offs

- **[Trade-off]** Rate limiting por IP pode afetar usuários legítimos atrás de um NAT/proxy compartilhado (ex.: uma rede corporativa) que gera muitas tentativas de contas diferentes do mesmo IP — mitigado escolhendo um limite generoso o suficiente para uso normal, mas que ainda bloqueie força bruta automatizada.
- **[Risco baixo]** Desabilitar `/docs` em produção dificulta depuração ad-hoc da API em produção pela equipe — mitigado permitindo habilitar via env quando necessário, sem precisar de redeploy de código.
