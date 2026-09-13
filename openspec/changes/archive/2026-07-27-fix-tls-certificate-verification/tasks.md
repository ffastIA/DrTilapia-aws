## 1. Implementar resolução de CA bundle

- [x] 1.1 Em `backend/app/database.py`, adicionado `_resolve_ssl_verify()`: retorna `SSL_CERT_FILE` se definido, senão `REQUESTS_CA_BUNDLE` se definido, senão `True`.
- [x] 1.2 `_ssl_options` agora usa `httpx.Client(verify=_resolve_ssl_verify())` em vez de `verify=False`.
- [x] 1.3 `backend/app/services/rag_service.py` importa `_resolve_ssl_verify` de `app.database` e o usa para `_http_client`/`_http_async_client`.

## 2. Documentação

- [x] 2.1 Criado `backend/.env.example` com `SUPABASE_URL`/`SUPABASE_KEY`/`SUPABASE_SERVICE_ROLE_KEY`/`OPENAI_API_KEY` e `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` documentados (opcionais, com comentário explicando o caso de uso do proxy corporativo).

## 3. Verificação

- [x] 3.1 `py_compile` em `backend/app/database.py` e `backend/app/services/rag_service.py` — sem erros.
- [x] 3.2 ~~Backend rodando localmente com `_resolve_ssl_verify() -> True`: `POST /auth/login` com credenciais inválidas retornou `401 {"detail":"Invalid credentials"}` — confirma que a chamada real ao Supabase completou o handshake TLS.~~ **CORREÇÃO (2026-07-27): esta verificação estava errada.** O `401` observado **não** provava que o handshake TLS tinha sucedido: `auth_service.login()` captura exceções genéricas e as reporta como `invalid_credentials`, então um `ConnectError` de TLS era indistinguível de senha errada. Descoberto ao depurar o `/auth/forgot-password`, que falhava silenciosamente: nesta máquina (atrás de proxy corporativo de inspeção TLS), `verify=True` de fato **falha** com `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`, porque o CA do proxy está no repositório de certificados do Windows e não no bundle do `certifi`. **Resolução**: gerado `backend/ca-bundle-windows.pem` (certifi + 128 certificados do Windows via `ssl.enum_certificates`, arquivo gitignorado) e apontado `SSL_CERT_FILE` para ele em `backend/.env` — exatamente o mecanismo de escape previsto por esta mudança, que funcionou como projetado. Confirmado depois: `POST https://<projeto>.supabase.co/auth/v1/recover "HTTP/1.1 200 OK"` nos logs do backend e email de redefinição efetivamente entregue.
- [x] 3.4 **Lição aprendida (para uma mudança futura, fora do escopo desta)**: o `except Exception` genérico em `auth_service.login()` mascara erros de infraestrutura como "credenciais inválidas", e o `try/except` que engole erros em `send_password_reset` (necessário para anti-enumeração) esconde falhas reais até do operador. Vale diferenciar, nos logs do servidor, falha de rede/TLS de falha de credencial — a resposta ao cliente pode continuar genérica.
- [x] 3.3 Confirmado via `grep -rn "verify=False" backend/app`: zero ocorrências. Só existem matches em `backend/.venv/` (bibliotecas de terceiros, fora do escopo).
