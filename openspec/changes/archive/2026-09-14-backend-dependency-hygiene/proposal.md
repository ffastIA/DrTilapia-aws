## Why

`backend/requirements.txt` (confirmado nesta sessão) pina `python-multipart==0.0.9`, versão afetada pela CVE-2024-53981 (DoS via parsing de multipart malformado), usada implicitamente por todo endpoint que recebe `UploadFile`/`File(...)` no FastAPI — corrigida a partir de 0.0.18. O mesmo arquivo pina `python-jose[cryptography]==3.3.0` (CVE-2024-33663, CVE-2024-33664) e `bcrypt==4.1.2`, mas nenhum dos dois é importado em lugar nenhum de `backend/app` (confirmado: `grep -r "import jose\|from jose\|import bcrypt" backend --include=*.py` não retorna nenhuma ocorrência) — são peso morto que aumenta a superfície de CVEs sem trazer nenhum benefício funcional. `sqlalchemy==2.0.29` e `sqlmodel>=0.0.22` também estão listados, mas o projeto não usa nenhum ORM — toda persistência passa pelo cliente `supabase-py` (REST/PostgREST) — confirmado que não há `models/` nem uso de `sqlalchemy`/`sqlmodel` em `backend/app`.

## What Changes

- Atualizar `python-multipart` para `>=0.0.18` em `backend/requirements.txt`.
- Remover `python-jose[cryptography]`, `bcrypt`, `sqlalchemy` e `sqlmodel` de `backend/requirements.txt` (dependências confirmadas não importadas por nenhum módulo em `backend/app`).
- Reinstalar o ambiente a partir do `requirements.txt` atualizado e rodar a suíte de testes para confirmar que nada dependia transitivamente dessas bibliotecas.

## Capabilities

### New Capabilities
- `backend-dependency-hygiene`: o conjunto de dependências Python do backend não inclui versões com CVE conhecida sem correção disponível, nem pacotes não utilizados pelo código da aplicação.

## Impact

- **Código afetado**: apenas `backend/requirements.txt` (nenhuma mudança de código de aplicação esperada, já que as dependências removidas não são importadas).
- **Build/CI**: a imagem Docker de produção instala menos pacotes (build mais rápido, imagem menor).
- **Risco**: baixo — a remoção é de pacotes comprovadamente não utilizados; o bump de `python-multipart` é uma versão mais nova da mesma biblioteca já em uso, sem mudança de API relevante para o uso atual (upload de arquivos via FastAPI).
