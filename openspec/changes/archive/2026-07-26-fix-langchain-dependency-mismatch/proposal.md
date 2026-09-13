## Why

O backend não consegue nem ser importado hoje: `from langchain_openai import ChatOpenAI, OpenAIEmbeddings` (usado em `backend/app/services/rag_service.py`) falha com `ModuleNotFoundError: No module named 'langchain_core.pydantic_v1'`. Isso bloqueou a verificação manual (tasks 4.1–4.5) da mudança anterior (`secure-admin-endpoints-and-fix-cleanup-dryrun`). Investigando a causa raiz: o Python usado para rodar este backend é a instalação **global/de usuário** (`C:\Users\usuario\AppData\Local\Programs\Python\Python311`), compartilhada com outras ferramentas não relacionadas a este projeto (`langgraph`, `langgraph-checkpoint`, `langgraph-prebuilt`, `langchain-chroma`). Essas ferramentas exigem `langchain-core` na série 1.x/2.x, enquanto `backend/requirements.txt` pina `langchain==0.1.12`, `langchain-community==0.0.28` e `langchain-openai==0.0.8`, que exigem `langchain-core>=0.1.27,<0.2.0` — **não existe uma versão de `langchain-core` que satisfaça os dois lados ao mesmo tempo**. Testei isso na prática: fixar `langchain-core==0.1.31` resolve o backend, mas quebra `langchain-chroma`/`langgraph*` (confirmado via `pip install`, revertido em seguida). Também há outras dependências do backend já fora do pin em `requirements.txt` no ambiente global (`pydantic`, `httpx`, `numpy`, `websockets`), sinal de que este projeto nunca teve um ambiente isolado de fato.

## What Changes

- Criar um ambiente virtual Python isolado (`backend/.venv`) dedicado exclusivamente a este backend, para eliminar o conflito com pacotes de outros projetos instalados globalmente.
- Instalar exatamente as versões de `backend/requirements.txt` dentro desse venv (sem tocar no Python global, que permanece intacto para as outras ferramentas).
- Verificar que `import app.main` funciona dentro do venv e que o servidor FastAPI sobe (`uvicorn app.main:app`).
- Documentar (README/instruções mínimas) como ativar o venv para rodar o backend, para que a próxima pessoa (ou eu, em sessões futuras) não volte a instalar dependências no Python global por engano.
- Não alterar nenhuma versão de pacote em `requirements.txt` nem migrar para LangChain 1.x — é uma mudança maior, com API quebrada em relação ao código atual de `rag_service.py`, fora do escopo desta correção pontual (fica registrada como melhoria futura).

## Capabilities

### New Capabilities
- `backend-isolated-runtime`: Garantia de que o backend roda em um ambiente Python isolado com exatamente as dependências pinadas em `requirements.txt`, sem depender nem conflitar com pacotes instalados globalmente para outros projetos.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: nenhuma mudança de código Python do backend; apenas ambiente de execução (novo diretório `backend/.venv`, não versionado) e, se necessário, uma entrada em `.gitignore` para excluir `.venv/`.
- **Execução**: a partir desta mudança, o backend deve ser iniciado usando o Python do `backend/.venv`, não o Python global.
- **Outros projetos**: nenhum impacto — o Python global e os pacotes `langgraph`/`langchain-chroma` de outras ferramentas permanecem exatamente como estavam (já revertido/confirmado nesta sessão).
- **Verificação manual pendente**: com o backend importável e executável, torna-se possível retomar as tasks 4.1–4.5 da mudança `secure-admin-endpoints-and-fix-cleanup-dryrun` (ainda dependem de o projeto Supabase estar ativo para testes contra dados reais).
