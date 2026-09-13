## Context

Dois arquivos `.env` distintos, nunca reconciliados:

`backend/.env` (efetivamente usado — `backend/app/database.py:15-16` carrega este caminho quando rodando localmente):
```
SUPABASE_URL=<projeto tfdripphcwbjiveksuet>
SUPABASE_KEY=<anon, correto>
SECRET_KEY=<idêntico a SUPABASE_SERVICE_ROLE_KEY>
OPENAI_API_KEY=<...>
SUPABASE_SERVICE_ROLE_KEY=<service_role>
```

`.env` da raiz (não carregado por nenhum código Python hoje — confirmado por `grep` exaustivo: `JWT_SECRET`, `SUPABASE_DB_PASSWORD`, `SUPABASE_DATABASE_URL`, `SUPABASE_ANON_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `RAG_STORAGE_BUCKET` têm **zero** ocorrências em `backend/` ou `frontend/` fora do próprio arquivo `.env`):
```
SUPABASE_ANON_KEY=<...>
SUPABASE_URL=<projeto cfupucrcnyqpimrsmbws — DIFERENTE do backend/.env>
SUPABASE_KEY=<role: service_role — deveria ser anon>
JWT_SECRET=<role: service_role — outro JWT de alto privilégio, não usado em lugar nenhum>
OPENAI_API_KEY=<...>
ALGORITHM=...
ACCESS_TOKEN_EXPIRE_MINUTES=...
ENVIRONMENT=...
SUPABASE_DB_HOST=...
SUPABASE_DB_PORT=...
SUPABASE_DB_NAME=...
SUPABASE_DB_USER=...
SUPABASE_DB_PASSWORD=<credencial direta de Postgres>
SUPABASE_DATABASE_URL=<connection string direta, com senha embutida>
//SUPABASE_SERVICE_ROLE_KEY=<comentado — nunca definido de fato>
RAG_STORAGE_BUCKET=...
```

`backend/docker-compose.yml:9-12`:
```yaml
    volumes:
      - .:/app
      - ../.env:/app/.env
    env_file:
      - ../.env
```
Dentro do container, `Path(__file__).resolve().parent.parent` (chamado a partir de `/app/app/database.py`) resolve para `/app`, então `env_path = /app/.env` — exatamente o arquivo montado pelo compose, que é o `.env` da raiz, **não** o `backend/.env`. Como esse arquivo tem `SUPABASE_SERVICE_ROLE_KEY` comentado, `database.py:28-34` levantaria `ValueError` na inicialização — o container, como está configurado, nunca sobe com sucesso.

Esta sessão já colou a chave `service_role` do projeto `tfdripphcwbjiveksuet` em texto puro no chat (necessário para diagnosticar/corrigir um bug anterior) — por convenção de segurança, um segredo colado em uma conversa deve ser considerado potencialmente exposto e rotacionado, independentemente de quão controlado o canal pareça.

## Goals / Non-Goals

**Goals:**
- Um único projeto Supabase referenciado de forma consistente em toda a configuração.
- Cada variável contém a chave do nível de privilégio correto (`anon` onde se espera baixo privilégio, `service_role` só onde necessário).
- Nenhuma credencial de banco de dados direta (usuário/senha/connection string do Postgres) presente em arquivo de configuração da aplicação, já que a aplicação nunca se conecta diretamente ao Postgres (só via API Supabase/PostgREST).
- `docker-compose.yml` referencia o arquivo `.env` que o código realmente espera.
- A chave `service_role` exposta nesta conversa é rotacionada.

**Non-Goals:**
- Não migrar a aplicação para usar variáveis de ambiente de uma central de segredos (Vault, AWS Secrets Manager, etc.) — fora de escopo desta correção pontual de higiene.
- Não remover `python-jose`/`bcrypt` do `requirements.txt` (dependências não usadas relacionadas a `JWT_SECRET`/`ALGORITHM`) — isso é H5 no relatório de auditoria, tratado como mudança separada se o time optar por fazê-la.
- Não automatizar a rotação de chave via API/MCP — não há ferramenta disponível para isso nesta sessão; é uma ação manual no Supabase Dashboard.

## Decisions

1. **Rotacionar a `service_role` (e, por precaução, a `anon`) do projeto `tfdripphcwbjiveksuet` no Supabase Dashboard.** Ação manual do usuário, não automatizável nesta mudança. Após rotacionar, atualizar `backend/.env` com os novos valores e reiniciar o backend.
2. **Consolidar em um único `.env`, o de `backend/`, que já é o efetivamente usado.** O `.env` da raiz deixa de ser necessário — como nenhum código o lê hoje, a decisão mais simples e segura é esvaziá-lo das credenciais sensíveis (rotacionadas) e do projeto duplicado/errado, mantendo só o que for genuinamente necessário para alguma ferramenta externa que dependa dele (a verificar durante a implementação; se nada depender, o arquivo pode ser removido do controle de versão/disco por decisão do usuário, fora do escopo automatizável aqui).
3. **`backend/docker-compose.yml`: trocar `../.env:/app/.env` e `env_file: ../.env` por `./.env:/app/.env` e `env_file: ./.env`** (o `.env` de `backend/`, já correto). Alternativa considerada: manter o `.env` da raiz e replicar as variáveis corretas nele. Rejeitada — mantém dois arquivos como fonte de verdade, exatamente o problema que causou a divergência atual.
4. **Remover `SECRET_KEY` de `backend/.env`** (cópia não utilizada da `service_role`) e remover `SUPABASE_DB_PASSWORD`/`SUPABASE_DATABASE_URL`/`JWT_SECRET` do `.env` da raiz (nenhum é lido por código).

## Risks / Trade-offs

- **[Risco] Rotacionar a chave `service_role` invalida imediatamente qualquer processo rodando com a chave antiga** → Mitigação: comunicar antes de rotacionar; atualizar `backend/.env` e reiniciar o backend logo em seguida, na mesma janela de manutenção.
- **[Risco] Alguma ferramenta externa (script, CI) pode depender do `.env` da raiz hoje sem que isso apareça em uma busca por `.py`/`.ts`** → Mitigação: buscar também por referências em `docker-compose.yml`, `Dockerfile`, scripts `.sh`/`.ps1` e workflows de CI antes de remover o arquivo por completo; nesta mudança, o conteúdo sensível é removido/corrigido primeiro, a remoção do arquivo em si é opcional e só se nada mais depender dele.
- **[Trade-off] Não elimina o hábito de duplicar `.env`s** — é uma correção pontual; uma prática de "um único `.env` versionado como exemplo, nunca committed" já existe via `.gitignore`, e isso é suficiente para o escopo atual.
