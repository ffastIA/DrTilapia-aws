## Context

`VectorAdminService` (`backend/app/services/vector_admin_service.py`) é uma fachada fina sobre `VectorAdminRepository`: cada método público (`get_files`, `get_file`, `get_file_chunks`, `get_file_content`, `get_file_diagnosis`, `delete_file`, `cleanup`) tenta, via `_call_repo_method`, uma lista fixa de nomes alternativos no repositório, e levanta `NotImplementedError` se nenhum bater. Essa indireção tolera que o repositório use nomes diferentes do serviço — mas exige manter as duas listas sincronizadas manualmente.

`get_file_diagnosis` ficou com a lista `['get_file_diagnosis', 'diagnose_file', 'get_diagnosis']`, nenhum dos quais existe no repositório — o método real lá é `diagnose_file_recovery` (`vector_admin_repository.py:269`), que calcula se o conteúdo de um arquivo é recuperável a partir da tabela `documents` e/ou do Storage (contagem de chunks ativos/deletados, flags `recoverable_from_table`/`recoverable_from_storage`/`recoverable_from_both`/`recoverable_from_none`).

## Goals / Non-Goals

**Goals:**
- `GET /admin/vector-base/files/{id}/diagnosis` retorna o diagnóstico real (200), não mais 500.
- Os 2 testes que já validavam comportamento correto (`get_files`/`get_file_content`, via seus aliases já presentes) passam a monkeypatchar o método público real da fachada, não um nome que nunca existiu nela.

**Non-Goals:**
- Não implementar `reindex_files`/`POST /admin/vector-base/reindex` — feature nova, fora do escopo (ver `proposal.md`).
- Não refatorar o padrão de `_call_repo_method`/listas de alias — funciona para os outros 5 métodos; o problema aqui é só uma lista desatualizada, não o padrão em si.

## Decisions

1. **Corrigir a lista de aliases, não trocar o nome do método no repositório.** Renomear `diagnose_file_recovery` no repositório para `get_file_diagnosis` também resolveria, mas arriscaria quebrar qualquer outro chamador direto do repositório (ex.: scripts, testes de repositório) sem necessidade — adicionar o nome à lista de aliases já existente é a mudança mínima e no mesmo padrão usado pelos outros 5 métodos da fachada.
2. **Corrigir os 3 mocks de teste para o nome público da fachada (`get_files`/`get_file_content`/`get_file_diagnosis`), nunca o nome interno do repositório** — os testes devem validar o contrato público de `VectorAdminService`, que é o que `main.py` de fato chama.

## Risks / Trade-offs

- Nenhum risco relevante — a mudança de produção é uma lista de strings (sem lógica nova), e os testes passam a exercitar o caminho real em vez de um monkeypatch que nunca era chamado.
