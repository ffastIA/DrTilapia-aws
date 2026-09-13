## Why

Todo o tráfego do backend para o Supabase (`backend/app/database.py:50`) e para a OpenAI (`backend/app/services/rag_service.py:65-66`) roda com verificação de certificado TLS **desabilitada incondicionalmente** (`httpx.Client(verify=False)` / `httpx.AsyncClient(verify=False)`). Isso foi introduzido como contorno para um proxy corporativo de inspeção TLS, mas não tem nenhum gate por ambiente — vale igualmente em desenvolvimento e em produção. Como consequência, a chave `service_role` do Supabase e a `OPENAI_API_KEY` trafegam por um canal que não verifica a identidade do servidor, tornando o backend vulnerável a um ataque man-in-the-middle caso rode fora da rede confiável com o proxy de inspeção (por exemplo, em produção na nuvem).

## What Changes

- `backend/app/database.py`: substituir `verify=False` por verificação real, resolvendo o CA bundle a partir de uma variável de ambiente (`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`, já suportadas nativamente pelo `httpx`/`certifi`) em vez de desabilitar a verificação.
- `backend/app/services/rag_service.py`: mesma correção para os clientes `httpx.Client`/`httpx.AsyncClient` passados a `OpenAIEmbeddings`/`ChatOpenAI`.
- Quando nenhuma variável de CA bundle estiver definida, os clientes usam a verificação TLS padrão (comportamento seguro por padrão); a exceção documentada (proxy corporativo local) passa a ser opt-in via env, nunca o padrão.
- Sem mudança de contrato de API — puramente configuração de transporte.

## Capabilities

### New Capabilities
- `backend-tls-verification`: Garantia de que todo tráfego HTTPS do backend (Supabase e OpenAI) verifica o certificado do servidor por padrão, com bypass apenas explícito e opt-in via variável de ambiente para ambientes de desenvolvimento atrás de proxy de inspeção TLS.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: `backend/app/database.py`, `backend/app/services/rag_service.py`.
- **Configuração**: nova variável de ambiente opcional (ex.: `HTTPX_CA_BUNDLE` ou reaproveitar `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` padrão do ecossistema Python) para apontar o CA bundle do proxy corporativo, quando necessário.
- **Comportamento observável**: em ambientes sem a variável configurada, chamadas ao Supabase/OpenAI passam a validar o certificado do servidor (podem falhar se o ambiente realmente depender do proxy de inspeção sem o CA correto configurado — mitigado documentando a variável de ambiente necessária).
- **Sem mudança de schema, banco ou frontend.**
