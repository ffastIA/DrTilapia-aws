## Why

`backend/app/main.py` embute `str(e)` diretamente no `detail` da resposta HTTP em 28 ocorrências (confirmado via busca no arquivo atual), cobrindo praticamente todo endpoint autenticado e alguns públicos. Quando a exceção capturada vem de uma biblioteca interna (`supabase-py`/PostgREST, `httpx`, o cliente OpenAI), essa string pode conter nomes de tabela/coluna/constraint do banco, mensagens de erro de rede/TLS com hostnames internos, ou detalhes de configuração — informação que ajuda um atacante a mapear a superfície interna do sistema e não deveria sair do servidor.

## What Changes

- Nos blocos `except Exception as e:` que capturam falhas genuinamente inesperadas (erros de biblioteca/infraestrutura, não validações de negócio deliberadas), substituir `detail=f"...: {str(e)}"` por uma mensagem genérica e estável para o cliente (ex.: `"Erro interno. Tente novamente mais tarde."`), preservando `str(e)` apenas no log do servidor via `logger.exception(...)`.
- Auditar cada uma das 28 ocorrências individualmente: onde o `str(e)` já é uma mensagem de negócio deliberada e segura (ex.: uma `ValueError` levantada pelo próprio código da aplicação com texto pensado para o usuário final, como `"Arquivo inválido"`), manter como está — a mudança é sobre não vazar exceções de terceiros, não sobre reescrever toda mensagem de erro.
- Padronizar o código de status HTTP de cada caso revisado (alguns 500 hoje podem ser, na verdade, erros de validação/entrada do cliente que deveriam ser 400/422).

## Capabilities

### New Capabilities
- `error-response-sanitization`: respostas de erro do backend nunca incluem a representação em string de uma exceção de biblioteca/infraestrutura de terceiros; o detalhe completo é sempre logado no servidor.

## Impact

- **Código afetado**: `backend/app/main.py` (todas as 28 ocorrências de `str(e)`), possivelmente `backend/app/services/*.py` se alguma exceção precisar de uma mensagem de domínio mais clara antes de chegar ao handler.
- **Comportamento observável**: clientes deixam de receber texto de exceção interna; continuam recebendo o mesmo código de status HTTP (exceto os poucos casos onde o status também estava incorreto) e uma mensagem genérica e estável.
- **Logs**: todo erro inesperado passa a ter `logger.exception(...)` (stack trace completo) no servidor, preservando a capacidade de diagnóstico que hoje só existe implicitamente pela resposta ao cliente.
