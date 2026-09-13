## Context

`backend/app/database.py:49-54`:
```python
# Bypass SSL corporativo (proxy de inspeção TLS)
_ssl_options = ClientOptions(httpx_client=httpx.Client(verify=False))

supabase_auth: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=_ssl_options)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, options=_ssl_options)
```
`backend/app/services/rag_service.py:64-79`:
```python
_http_client = httpx.Client(verify=False)
_http_async_client = httpx.AsyncClient(verify=False)

self.embeddings = OpenAIEmbeddings(..., http_client=_http_client, http_async_client=_http_async_client)
self.llm = ChatOpenAI(..., http_client=_http_client, http_async_client=_http_async_client)
```
`httpx.Client(verify=...)` aceita `True` (padrão, usa `certifi`), `False` (desabilita — o estado atual), ou uma **string com caminho para um CA bundle customizado** (equivalente a `ssl.create_default_context(cafile=...)`). Isso é exatamente o que se precisa para um proxy de inspeção TLS: confiar no certificado da CA do proxy, sem desabilitar a verificação por completo.

Esta sessão já resolveu um problema de causa raiz semelhante em outra parte do projeto (o ambiente Python local também está atrás de um proxy de inspeção), usando o pacote `truststore` para delegar a verificação ao repositório de certificados do próprio SO. Para o backend em produção/CI, a abordagem mais portável e sem dependência nova é aceitar um caminho de arquivo CA via variável de ambiente.

## Goals / Non-Goals

**Goals:**
- Nenhum cliente HTTP do backend desabilita verificação de certificado por padrão.
- Ambientes que realmente precisam confiar em uma CA de proxy corporativo continuam funcionando, de forma explícita e documentada.
- A mudança é puramente de transporte — nenhum comportamento de negócio muda.

**Non-Goals:**
- Não introduzir `truststore` como dependência do backend nesta mudança (é uma solução mais pesada, adequada ao ambiente de desenvolvimento local desta sessão, não necessariamente ao runtime de produção/CI do projeto). Pode ser reavaliado depois se o time preferir.
- Não alterar `docker-compose.yml`/`Dockerfile` para instalar um CA customizado na imagem — fica documentado como pré-requisito operacional, não implementado nesta mudança.

## Decisions

1. **Ler uma variável de ambiente opcional para o caminho do CA bundle e construir o `httpx.Client`/`httpx.AsyncClient` com `verify=<caminho ou True>`.**
   - Nome da variável: reaproveitar a convenção já padrão do ecossistema Python/`requests`/`httpx`: `SSL_CERT_FILE` (usada pelo módulo `ssl` nativo) ou `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` (convenção `requests`/`curl`, muitas libs HTTP em Python já checam essas). Como `httpx` não lê nenhuma delas automaticamente, o código do backend precisa ler explicitamente. Decisão: introduzir uma função utilitária pequena, `_resolve_ssl_verify()` em `backend/app/database.py`, que checa `SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE` nessa ordem, e usa `True` (padrão seguro) se nenhuma estiver definida.
   - Alternativa considerada: sempre exigir a variável e falhar se ausente. Rejeitada — quebraria qualquer ambiente que não esteja atrás do proxy corporativo (a maioria); o padrão seguro (`verify=True`) já é o comportamento correto quando não há proxy de inspeção.
2. **Reaproveitar a mesma função utilitária em `rag_service.py`**, evitando duplicar a lógica de resolução do CA bundle. Import de `backend/app/database.py` (já é uma dependência existente de `rag_service.py`).
3. **Manter os clientes `httpx.Client`/`httpx.AsyncClient` como estão hoje quanto a outras opções** (timeouts, etc.) — fora de escopo desta correção pontual de TLS.

## Risks / Trade-offs

- **[Risco] Em produção, se o ambiente realmente estiver atrás do proxy de inspeção sem a variável configurada, todas as chamadas ao Supabase/OpenAI passam a falhar por certificado não confiável** → Mitigação: documentar claramente a variável de ambiente no README/`.env.example` do backend; o erro resultante (`SSLCertVerificationError`) é explícito e diagnosticável, ao contrário do risco de segurança silencioso atual.
- **[Trade-off] Não resolve o problema de fundo (por que existe um proxy de inspeção TLS na rede)** — fora do controle desta mudança de código; a correção aqui é permitir operar corretamente COM o proxy, sem abrir mão da verificação.
