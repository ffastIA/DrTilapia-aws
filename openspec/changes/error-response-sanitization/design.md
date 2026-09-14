## Context

Padrão repetido em `backend/app/main.py` (exemplos, linhas atuais confirmadas nesta sessão):
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Erro no upload: {str(e)}")   # :233
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Erro ao executar cleanup: {str(e)}")  # :312
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))  # :444, :468, :642, :665, :682
```
Total: 28 ocorrências de `str(e)` no arquivo, em status codes 400/403/404/422/500 misturados. Nem todas são igualmente problemáticas — um `404`/`400` cujo `str(e)` vem de uma `ValueError`/`PermissionError` levantada pelo próprio código de serviço (ex.: `"Arquivo não encontrado"`, `"Você não tem permissão para excluir este recurso"`) já é uma mensagem de negócio segura. O risco real está nos `except Exception` genéricos que podem capturar qualquer exceção de biblioteca (rede, banco, parsing) e a devolvem verbatim.

## Goals / Non-Goals

**Goals:**
- Nenhuma resposta HTTP inclui a string de uma exceção de biblioteca/infraestrutura não controlada pela aplicação.
- Toda exceção inesperada é logada no servidor com stack trace completo antes de responder genericamente ao cliente.

**Non-Goals:**
- Não redesenhar todo o esquema de erros da API (ex.: introduzir um formato de erro padronizado `{code, message}`) — fora de escopo desta correção pontual; fica registrado como possível trabalho futuro.
- Não alterar comportamento de mensagens de negócio já seguras e deliberadas.

## Decisions

1. **Critério de triagem por ocorrência**: uma ocorrência é "insegura" (precisa de mensagem genérica) quando o bloco `except` captura `Exception` genérica sem um tipo específico de exceção de domínio conhecido — nesses casos, não há garantia de que `str(e)` seja uma mensagem pensada para o usuário. Ocorrências dentro de `except ValueError`/`except PermissionError`/exceções de domínio explícitas, cuja mensagem foi escrita pelo próprio código da aplicação, são consideradas seguras e mantidas.
2. **Mensagem genérica única**: usar uma constante compartilhada (ex.: `GENERIC_ERROR_MESSAGE = "Erro interno. Tente novamente mais tarde."`) em vez de strings ad-hoc por endpoint, para consistência e para facilitar auditoria futura (`grep` por essa constante confirma cobertura).
3. **Log antes de responder**: todo `except Exception` revisado passa a chamar `logger.exception(...)` (captura o traceback automaticamente) antes de levantar a `HTTPException` genérica.

## Risks / Trade-offs

- **[Trade-off]** Mensagens genéricas tornam depuração pelo cliente (ex.: um desenvolvedor de frontend testando manualmente) mais difícil — mitigado pelo log detalhado do lado do servidor, que deve ser acessível via CloudWatch Logs após a containerização.
- **[Risco de escopo]** Auditar 28 ocorrências individualmente é trabalho manual sujeito a julgamento; a tarefa de verificação (seção 3 de `tasks.md`) exige revisão caso a caso, não uma substituição textual em massa.
