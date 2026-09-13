## Context

`backend/app/services/fish_image_service.py:38-40`:
```python
class FishImageService:
    def __init__(self) -> None:
        self.supabase = supabase_admin
        self.bucket = BUCKET_NAME
```
`self.supabase` é usado tanto para `.table("fish_images"/"fish_analyses")` quanto para `.storage.from_(self.bucket)` — um único cliente `service_role`, um único singleton reusado por todas as requisições.

Confirmado ao vivo (RLS já existente, mudança anterior desta sessão não tocou nisso):
```
fish_images_select_own  | authenticated | SELECT | user_id = auth.uid()
fish_images_insert_own  | authenticated | INSERT | user_id = auth.uid()
fish_images_update_own  | authenticated | UPDATE | user_id = auth.uid()
fish_images_delete_own  | authenticated | DELETE | user_id = auth.uid()
fish_analyses_select_own / insert_own / update_own / delete_own  (idêntico, tabela fish_analyses)
```
Essas policies nunca disparam hoje porque toda consulta roda como `service_role`. O isolamento real é só Python: `fish_image_service.py:240-241` (`delete_image`) e equivalente em `delete_analysis`, além de `main.py:426-434` (checagem inline em `/fish/analyses/process`).

**Achado importante durante o design desta mudança:** `select policyname from pg_policies where schemaname='storage' and tablename='objects'` retorna **vazio** — não existe nenhuma policy de RLS para `storage.objects` (bucket `fish-images` incluído). Como o Storage do Supabase tem RLS habilitada por padrão em `storage.objects`, **zero policies = acesso negado por padrão** para qualquer papel que não seja `service_role`. Isso significa que trocar o cliente usado para as chamadas de Storage (`upload`, `download`, `remove`, `create_signed_url`) quebraria completamente o upload/visualização de imagens. Portanto, **o Storage continua via `service_role` nesta mudança** — só as consultas às tabelas `fish_images`/`fish_analyses` passam a usar um cliente escopado ao usuário. Adicionar policies de Storage é trabalho futuro, fora deste escopo.

`backend/app/dependencies.py:40-45` já retorna o `access_token` do usuário autenticado no dicionário de `get_current_user`:
```python
return {
    'id': user_data['id'],
    'email': user_data['email'],
    'role': user_data['role'],
    'access_token': access_token
}
```
— ou seja, todo endpoint `/fish/*` já tem o token disponível via `current_user['access_token']`, sem precisar de nenhuma mudança de autenticação.

## Goals / Non-Goals

**Goals:**
- Leituras/escritas em `fish_images`/`fish_analyses` passam a rodar com um cliente autenticado como o usuário chamador, ativando as policies de RLS de posse já existentes e corretas.
- As checagens de propriedade em Python continuam existindo, como defesa em profundidade — não são removidas.
- Nenhuma mudança de comportamento observável para uso legítimo.

**Non-Goals:**
- Não mexer em Storage (`fish-images` bucket) nesta mudança — permanece via `service_role`, pela ausência de policies de RLS em `storage.objects` (ver achado acima). Adicionar essas policies é uma mudança separada e maior (schema de Storage + testes de upload/download).
- Não aplicar o mesmo padrão a `videos` — tabela sem RLS de posse por usuário (é conteúdo compartilhado por design: qualquer usuário autenticado pode listar, só admin pode mutar). Tratar como recurso compartilhado é uma decisão de produto, não um bug — fica registrado como decisão explícita, não como pendência.
- Não aplicar a `documents`/RAG — não tem conceito de "dono" individual (é uma base de conhecimento institucional compartilhada, gerenciada só por admins).
- Não alterar `dependencies.py`/`auth_service.py`/`rag_service.py`/`vector_admin_repository.py` — permanecem em `service_role`, que é apropriado para os casos de uso deles (lookup de role no login, base RAG administrada centralmente).

## Decisions

1. **Introduzir uma função utilitária para criar um cliente Supabase autenticado como o usuário chamador**, em `backend/app/database.py`: `get_user_scoped_client(access_token: str) -> Client`, construindo com a `anon key` (`SUPABASE_KEY`) e chamando `.postgrest.auth(access_token)` (API padrão do `supabase-py` para autenticar requisições PostgREST subsequentes com um JWT de usuário, ativando RLS como aquele usuário).
   - Reaproveita o mesmo padrão de "cliente por requisição, sem estado compartilhado" já usado nesta sessão para isolar o login (`isolate-login-client-and-fix-users-rls`).
2. **`FishImageService` deixa de ter um único `self.supabase` fixo para tudo.** Mantém `self.supabase_admin` (era `self.supabase`) só para Storage. Os métodos que consultam/gravam `fish_images`/`fish_analyses` (`upload_image`, `list_images`, `list_analyses`, `delete_image`, `delete_analysis`) passam a receber um parâmetro `access_token: str` e usar `get_user_scoped_client(access_token).table(...)` para essas chamadas específicas, mantendo `self.supabase_admin.storage...` para as operações de arquivo.
3. **`backend/app/main.py`**: cada endpoint `/fish/*` passa `current_user['access_token']` para o método correspondente do serviço.
4. **Checagens de propriedade em Python permanecem inalteradas** (`fish_image_service.py:240-241` e o trecho em `main.py:426-434`) — com RLS ativa, elas se tornam redundantes na maior parte dos casos, mas continuam sendo uma segunda camada válida e barata de manter.

## Risks / Trade-offs

- **[Risco] `postgrest.auth(access_token)` expira quando o token expira** — uma chamada com token expirado retorna erro do PostgREST (401/403), que já cai nos blocos de tratamento de exceção existentes em `main.py`. Comportamento aceitável: o usuário precisa reautenticar, igual a qualquer chamada autenticada hoje.
- **[Trade-off] Mais uma dependência de rede por chamada (nenhuma, na verdade)** — não há round-trip extra: o cliente escopado ao usuário faz a mesma quantidade de chamadas HTTP que o cliente admin fazia, só com um header de autorização diferente.
- **[Risco] Se uma policy de RLS estiver mal escrita, uma operação legítima passa a falhar silenciosamente (0 linhas) em vez de um erro claro** — mitigado pelas policies já estarem confirmadas corretas nesta sessão (auditoria ao vivo); qualquer regressão apareceria imediatamente nos testes manuais da seção de Verificação.
- **[Trade-off] Storage continua sem RLS de posse (`service_role` para tudo)** — aceito como não-goal explícito; documentado para uma mudança futura dedicada.
