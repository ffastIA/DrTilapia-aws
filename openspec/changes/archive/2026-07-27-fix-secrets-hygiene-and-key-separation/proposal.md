## Why

Encontrados três problemas distintos de higiene de segredos:

1. **`backend/.env`**: `SECRET_KEY` é **byte-a-byte idêntico** a `SUPABASE_SERVICE_ROLE_KEY` (mesmo JWT, mesmo `role: service_role`) — não é usado por nenhum código (`grep` confirma zero referências a `SECRET_KEY` em `backend/app`), mas é uma cópia redundante e desnecessária de um segredo de alto privilégio.
2. **`.env` da raiz**: `SUPABASE_KEY` ali é, na verdade, um JWT `role: service_role` (deveria ser a chave `anon`, de baixo privilégio); `JWT_SECRET` também é um JWT `service_role`; o arquivo ainda contém `SUPABASE_DB_PASSWORD` e `SUPABASE_DATABASE_URL` — credenciais diretas de superusuário do Postgres, nunca necessárias para a aplicação rodar (que só fala com Supabase via API/PostgREST, nunca com conexão direta ao banco). Além disso, `SUPABASE_URL` nesse arquivo aponta para um **projeto Supabase diferente** do usado por `backend/.env` (`cfupucrcnyqpimrsmbws` vs `tfdripphcwbjiveksuet`).
3. **`backend/docker-compose.yml:9-12`** monta esse `.env` da raiz diretamente em `/app/.env` (`../.env:/app/.env` + `env_file: ../.env`) — que é exatamente o caminho que `backend/app/database.py:15` resolve quando rodando dentro do container. Como esse arquivo tem `SUPABASE_SERVICE_ROLE_KEY` comentado (`//SUPABASE_SERVICE_ROLE_KEY=...`), **o container, como configurado hoje, falharia ao subir** (`database.py:28-34` lança `ValueError` se a variável não estiver definida) — nunca testado de ponta a ponta com o compose atual, ou testado com um `.env` diferente do versionado.

Adicionalmente: a chave `SUPABASE_SERVICE_ROLE_KEY` do projeto `tfdripphcwbjiveksuet` foi colada em texto puro nesta conversa em uma sessão anterior (para permitir a correção de um outro bug). Chaves coladas em uma conversa de chat devem ser tratadas como potencialmente expostas.

## What Changes

- **Rotação de chaves** (ação manual, feita por você no Supabase Dashboard — não pode ser automatizada por esta mudança): gerar novas chaves `anon`/`service_role` para o projeto `tfdripphcwbjiveksuet`, já que a `service_role` atual foi exposta em texto puro nesta conversa.
- `backend/.env`: remover a linha `SECRET_KEY` (não usada por nenhum código).
- `.env` da raiz: corrigir para apontar para o mesmo projeto Supabase (`tfdripphcwbjiveksuet`) e usar a chave `anon` correta em `SUPABASE_KEY` (não `service_role`); remover `SUPABASE_DB_PASSWORD`/`SUPABASE_DATABASE_URL` (não usadas pela aplicação); remover `JWT_SECRET` órfão (se confirmado não usado — ver Verificação).
- `backend/docker-compose.yml`: parar de montar o `.env` da raiz; usar `backend/.env` (o arquivo que `database.py` já espera) como `env_file`, ou copiar `backend/.env` como parte do processo de build/execução do container.
- Nenhuma mudança de código Python — só arquivos de configuração/ambiente e uma ação manual de rotação de chave.

## Capabilities

### New Capabilities
- `backend-secrets-hygiene`: Garantia de que os arquivos de ambiente do projeto (raiz e `backend/`) apontam para um único projeto Supabase, usam a chave de privilégio correta em cada variável (`anon` vs `service_role`), não duplicam segredos sem necessidade, e não contêm credenciais de banco de dados não utilizadas pela aplicação; e de que a configuração do container Docker referencia o arquivo `.env` correto.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: nenhum arquivo `.py`. Apenas `backend/.env`, `.env` (raiz), `backend/docker-compose.yml`.
- **Ação manual necessária (fora do escopo de código, mas parte desta mudança):** rotacionar as chaves `anon`/`service_role` do projeto `tfdripphcwbjiveksuet` no Supabase Dashboard, e atualizar `backend/.env` com os novos valores.
- **Comportamento observável**: nenhuma mudança funcional para o app rodando localmente fora do Docker (já usa `backend/.env` corretamente). O container Docker passa a poder subir com a configuração versionada (hoje falharia).
- **Risco de execução**: rotacionar a `service_role` invalida a chave atual imediatamente — qualquer processo rodando com a chave antiga (ex.: o servidor local desta sessão) para de autenticar até ser reiniciado com a chave nova. Deve ser coordenado (avisar antes de rotacionar, atualizar `.env` e reiniciar o backend em seguida).
