## Why

`POST /auth/login` (`backend/app/main.py:100`) não tem nenhum limite de tentativas — confirmado nesta sessão que não existe rate limiting, `slowapi`, ou lógica de lockout em `backend/app/`. Um atacante pode tentar credential-stuffing/força bruta contra qualquer conta na velocidade que sua rede permitir, sem fricção.

Separadamente, `app = FastAPI()` (`main.py:80`) é criado sem `docs_url`/`redoc_url`/`openapi_url` configurados, o que deixa `/docs`, `/redoc` e `/openapi.json` habilitados incondicionalmente em qualquer ambiente, incluindo produção — expondo publicamente o esquema completo da API (nomes de todo endpoint, incluindo os administrativos, seus parâmetros e modelos de request/response) a qualquer visitante não autenticado.

(Nota: outros dois pontos do item H6 original da auditoria — mapeamento de exceções de autenticação para 401 e log de erros — já estão implementados em `backend/app/dependencies.py:54-69`, `AuthApiError` é mapeada para 401 com log, e exceções genuínas para 500 com `logger.exception`; portanto não fazem parte do escopo desta mudança.)

## What Changes

- Adicionar rate limiting a `POST /auth/login` (e, se aplicável, `POST /auth/forgot-password`), por IP (e opcionalmente por email/identificador da tentativa), com um limite razoável (ex.: N tentativas por minuto) e resposta `429` ao exceder.
- Gatear `docs_url`/`redoc_url`/`openapi_url` do `FastAPI(...)` por uma variável de ambiente (ex.: `ENVIRONMENT`), desabilitados por padrão e habilitados apenas quando `ENVIRONMENT=development` (ou equivalente) explicitamente.

## Capabilities

### New Capabilities
- `auth-endpoint-hardening`: o endpoint de login tem proteção contra tentativas repetidas em alta velocidade, e a documentação interativa da API não fica exposta publicamente por padrão em produção.

## Impact

- **Código afetado**: `backend/app/main.py` (criação do `app = FastAPI()`, endpoint `/auth/login`).
- **Dependências**: nova dependência para rate limiting (ex.: `slowapi`, compatível com FastAPI/Starlette).
- **Configuração**: nova variável de ambiente para controlar exposição de `/docs`/`/redoc`/`/openapi.json`, documentada em `backend/.env.example`.
- **Comportamento observável**: tentativas de login legítimas (dentro do limite) não são afetadas; em produção, `/docs`/`/redoc`/`/openapi.json` passam a responder 404 a menos que explicitamente habilitados.
