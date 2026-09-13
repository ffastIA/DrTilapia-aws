## 1. Criar ambiente isolado

- [x] 1.1 Criar virtualenv em `backend/.venv` usando o Python já usado pelo projeto.
- [x] 1.2 Adicionar `backend/.venv/` ao `.gitignore` (não versionar o ambiente virtual). — já coberto pelo `.gitignore` raiz (`venv/`/`.venv/`); nenhuma alteração necessária.
- [x] 1.3 Instalar as dependências dentro do venv com `pip install -r backend/requirements.txt`, sem tocar no Python global.
- [x] 1.4 (descoberto durante a implementação) Pinar `gotrue==2.4.4` em `backend/requirements.txt`: `supabase==2.4.0` não pina `gotrue` (só declara `>=1.3,<3.0`), e a versão mais recente dentro desse range (`2.9.1`+) passa `proxy=` para `httpx.Client`, incompatível com `httpx==0.25.2`. Sem esse pin, uma instalação nova continuaria quebrando mesmo após esta correção.
- [x] 1.5 (descoberto durante a implementação) Resalvar `backend/requirements.txt` em UTF-8 simples (estava em UTF-16 com BOM); o arquivo já precisou ser reescrito para adicionar o pin de `gotrue`.

## 2. Verificar a correção

- [x] 2.1 Confirmar que `python -c "import app.main"` funciona usando o Python de `backend/.venv` (sem `ModuleNotFoundError` nem conflito de versão do LangChain/gotrue/httpx). Confirmado: `IMPORT OK`, todas as rotas listadas corretamente.
- [x] 2.2 Confirmar que `uvicorn app.main:app` inicializa sem erro usando o Python de `backend/.venv`. Confirmado: "Uvicorn running on http://127.0.0.1:8001", `GET /openapi.json` retornou 200.
- [x] 2.3 Confirmar que o Python global permanece com as mesmas versões de `langchain-core`/`langsmith`/demais pacotes que tinha antes desta mudança. Confirmado: `langchain-core` global permanece `1.3.2` e `langsmith` `0.7.37` (o teste inicial que os alterou foi revertido antes de qualquer instalação definitiva); todos os overrides (`langchain-core==0.1.31`, `langsmith==0.1.147`, `httpx==0.25.2`, `gotrue==2.4.4`) foram instalados apenas dentro de `backend/.venv` (pip recusou-se a desinstalar as versões globais, confirmando o isolamento).

## 3. Verificação manual bônus (desbloqueada por esta correção)

- [x] 3.1 Com o servidor rodando via `backend/.venv`, confirmar ao vivo que `/admin/vector-base/files`, `/admin/upload` e `/consultoria/chat` retornam 401 sem token (task 4.1 da mudança `secure-admin-endpoints-and-fix-cleanup-dryrun`, antes bloqueada por este bug de dependências).
