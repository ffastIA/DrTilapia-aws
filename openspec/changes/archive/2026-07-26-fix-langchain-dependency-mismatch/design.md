## Context

O backend (`backend/requirements.txt`) pina `langchain==0.1.12`, `langchain-community==0.0.28` e `langchain-openai==0.0.8`, todos da geração 0.1.x do LangChain (início de 2024), que exigem `langchain-core>=0.1.27,<0.2.0` (confirmado via metadata de cada pacote). O Python usado para rodar este backend, porém, é a instalação global de usuário (`C:\Users\usuario\AppData\Local\Programs\Python\Python311`), não um virtualenv dedicado. Esse Python global tem `langchain-core==1.3.2` instalado, exigido por outras ferramentas presentes no mesmo ambiente (`langgraph==1.1.10` exige `langchain-core<2,>=1.3.0`; `langgraph-prebuilt` exige `>=1.3.1`; `langchain-chroma==0.2.4` exige `>=0.3.60`). Não há nenhuma versão de `langchain-core` que satisfaça simultaneamente a trinca antiga do DrTilápia e essas ferramentas mais novas — é um conflito estrutural, não um pin desatualizado corrigível in-place.

Confirmado empiricamente nesta sessão: fixar `langchain-core==0.1.31` (dentro da faixa exigida pelo trio antigo) resolve o import do backend, mas imediatamente quebra `langchain-chroma`/`langgraph*` (erro de dependência do pip). A reversão para `langchain-core==1.3.2` (e `langsmith==0.7.37`, que também foi rebaixado como efeito colateral) foi aplicada e verificada, restaurando o ambiente global ao estado anterior a esta investigação.

Adicionalmente, o dry-run de `pip install -r requirements.txt` mostrou que `pydantic`, `httpx` e outras dependências já estão fora dos pins do projeto no ambiente global — evidência de que este backend nunca rodou de fato isolado, e vem "funcionando por acaso" com o que quer que esteja instalado globalmente no momento.

## Goals / Non-Goals

**Goals:**
- Fazer o backend importar e rodar (`uvicorn app.main:app`) com exatamente as versões pinadas em `requirements.txt`.
- Não quebrar nenhuma outra ferramenta que compartilha o Python global (`langgraph`, `langchain-chroma`, etc.).
- Deixar um caminho claro e repetível para rodar o backend (venv dedicado), evitando que o problema recorra.

**Non-Goals:**
- Não migrar `langchain`/`langchain-community`/`langchain-openai` para a série 1.x (mudança de API grande, precisaria reescrever trechos de `rag_service.py` e testar contra uma chave OpenAI real — fora do escopo desta correção pontual).
- Não modificar `requirements.txt` (as versões pinadas já são mutuamente compatíveis entre si; o problema é o ambiente de execução, não os pins).
- Não tentar reconciliar um único ambiente Python global para todos os projetos da máquina.

## Decisions

1. **Criar um virtualenv dedicado em `backend/.venv`** e instalar `pip install -r requirements.txt` dentro dele.
   - Alternativa considerada: fixar `langchain-core` no Python global. Rejeitada — testada e revertida nesta sessão porque quebra outras ferramentas (`langgraph`, `langchain-chroma`) que também vivem no mesmo Python global.
   - Alternativa considerada: usar `pipx` ou Docker. `docker-compose.yml`/`backend.Dockerfile` já existem no projeto (rota de produção legítima), mas para o ciclo de desenvolvimento local mais rápido, um venv padrão do Python é mais simples e não exige Docker Desktop rodando.
2. **Adicionar um único pin novo a `requirements.txt`: `gotrue==2.4.4`.** As três libs LangChain pinadas já são mutuamente consistentes (todas exigem `langchain-core` na faixa `0.1.x`), então não precisam de pin adicional. Porém, ao testar dentro do venv, a instalação de `supabase==2.4.0` (que não pina `gotrue`, apenas declara `gotrue>=1.3,<3.0`) resolveu `gotrue==2.9.1`, cujo cliente HTTP passa `proxy=` incondicionalmente para `httpx.Client(...)` — parâmetro que só existe em `httpx>=0.26`, incompatível com `httpx==0.25.2` (pin exigido tanto por `requirements.txt` quanto pelo próprio `supabase==2.4.0`, que declara `httpx>=0.24,<0.26`). Sem um pin explícito de `gotrue`, **qualquer instalação nova continuaria quebrando** mesmo depois desta correção, pois o resolvedor de dependências sempre buscaria a versão mais recente de `gotrue` dentro do range permitido por `supabase==2.4.0`. Testado e confirmado: `gotrue==2.4.4` (contemporâneo ao `supabase==2.4.0`) não passa `proxy=` nem `proxies=` ao construir seu cliente HTTP, funcionando com `httpx==0.25.2`.
3. **Adicionar `backend/.venv/` ao `.gitignore`** para não versionar o ambiente virtual.
4. **Verificar o resultado** com `python -c "import app.main"` dentro do venv e, se possível, subindo `uvicorn app.main:app --reload` momentaneamente para confirmar que a aplicação inicializa sem erro de import.

## Risks / Trade-offs

- **[Risco] Alguém pode continuar rodando o backend com o Python global por hábito** → Mitigação: documentar claramente (neste design e em instruções de execução) que o backend deve ser iniciado a partir de `backend/.venv`.
- **[Risco] O venv pode instalar uma versão de `langchain-core` ligeiramente diferente da que existia quando o projeto foi escrito** → Mitigação: `pip install -r requirements.txt` respeita os ranges declarados pelas próprias libs LangChain pinadas (`>=0.1.27,<0.2.0` / `>=0.1.28,<0.3` / `>=0.1.31,<0.2.0`), então qualquer versão resolvida é, por definição, uma que os autores dessas libs consideraram compatível.
- **[Trade-off] Não resolve a dívida técnica de dependências desatualizadas (LangChain 0.1.x, FastAPI 0.110, etc.)** apontada na auditoria original — deliberadamente fora de escopo aqui; migrar para versões modernas é um projeto à parte, com testes de regressão no pipeline de RAG.
- **[Efeito colateral positivo] `backend/requirements.txt` estava salvo em UTF-16 (BOM)**, apontado na auditoria original como item de qualidade. Como o arquivo precisou ser reescrito para adicionar o pin de `gotrue`, foi resalvo em UTF-8 simples no mesmo passo — não é um novo trabalho, apenas o arquivo já teve que ser tocado.
- **[Risco] Projeto Supabase pausado** → o projeto (`tfdripphcwbjiveksuet`) está `INACTIVE` nesta sessão; mesmo com o backend rodando localmente, chamadas reais a `/auth/login`, `/admin/*` etc. vão falhar até o projeto ser reativado. Isso é externo a esta correção e não é resolvido por ela.
