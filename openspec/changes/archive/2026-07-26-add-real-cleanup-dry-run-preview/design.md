## Context

Fluxo atual de `POST /admin/vector-base/cleanup` (`backend/app/main.py:214-226`):
```python
if request.dry_run is True and request.confirmation_phrase == "SIMULACAO":
    result = vector_admin_service.cleanup(True)
else:
    result = vector_admin_service.cleanup(request.confirmation_phrase)
```
`VectorAdminService.cleanup` (`backend/app/services/vector_admin_service.py:89-102`):
```python
def cleanup(self, confirmation_phrase: Union[str, bool] = True) -> Any:
    if isinstance(confirmation_phrase, bool):
        if confirmation_phrase:
            return {
                'total_files_processed': 0,
                'total_documents_deleted': 0,
                'total_ingestion_logs_deleted': 0,
                'total_storage_deleted': 0,
                'status': 'success',
                'message': 'Cleanup simulation executed.'
            }
        else:
            confirmation_phrase = 'CONFIRMAR_LIMPEZA_TOTAL'
    return self._call_repo_method(['cleanup', 'cleanup_vector_base', 'clear_vector_base'], confirmation_phrase)
```
Quando `dry_run=true`, o branch `if confirmation_phrase:` (True) devolve um dicionário **fixo**, sem consultar o banco. Isso é seguro (não apaga nada), mas inútil como simulação — um admin não tem como saber quantos arquivos realmente seriam afetados antes de confirmar a limpeza real.

`VectorAdminRepository.list_files()` (`backend/app/vector_admin_repository.py:176-196`) já agrupa os documentos por `original_file_id` e cada resumo já tem `total_chunks`, `storage_bucket`, `storage_path` — exatamente os dados necessários para calcular uma prévia real, sem precisar de nenhuma query nova para a contagem de documentos/storage. Falta apenas contar `ingestion_logs`/`rag_ingestion_logs` de forma não-destrutiva (hoje só existe `_best_effort_delete_ingestion_logs`, que deleta).

## Goals / Non-Goals

**Goals:**
- O modo simulação (`dry_run=true`) passa a refletir a realidade do banco: número de arquivos, documentos e objetos de storage que seriam removidos.
- Nenhuma chamada em modo simulação executa qualquer `DELETE`, em nenhuma tabela ou no Storage.
- A resposta explicita se foi simulação ou execução real (`dry_run: true`/`false`), sem quebrar clientes que ainda não leem esse campo.

**Non-Goals:**
- Não mudar a lógica de execução real (`cleanup_vector_base`) além de adicionar o campo `dry_run: False` ao seu retorno, por simetria.
- Não mudar o contrato de request (`CleanupVectorBaseRequest`) — `dry_run`/`confirmation_phrase` já funcionam como estão.
- Não tentar prever custos de operações do LangGraph/embeddings — o escopo é só contagem de linhas/objetos que seriam apagados.

## Decisions

1. **Novo método `VectorAdminRepository.preview_cleanup()`**, reaproveitando `list_files()`:
   ```python
   def preview_cleanup(self) -> Dict[str, Any]:
       files = self.list_files()
       total_files_processed = len(files)
       total_documents_deleted = sum(f['total_chunks'] for f in files)
       total_storage_deleted = sum(
           1 for f in files if f.get('storage_bucket') and f.get('storage_path')
       )
       total_ingestion_logs_deleted = sum(
           self._count_ingestion_logs(f['original_file_id']) for f in files
       )
       message = (
           f'Simulação concluída. Seriam processados: {total_files_processed} arquivos, '
           f'removidos: {total_documents_deleted} docs, {total_ingestion_logs_deleted} logs, '
           f'{total_storage_deleted} storages. Nenhum dado foi apagado.'
       )
       return {
           'total_files_processed': total_files_processed,
           'total_documents_deleted': total_documents_deleted,
           'total_ingestion_logs_deleted': total_ingestion_logs_deleted,
           'total_storage_deleted': total_storage_deleted,
           'dry_run': True,
           'status': 'success',
           'message': message,
       }
   ```
   - Alternativa considerada: calcular tudo dentro de `VectorAdminService.cleanup` sem um método novo no repositório. Rejeitada — o repositório já concentra toda a lógica de acesso a `documents`/`ingestion_logs`; manter a contagem lá segue o padrão existente (`list_files`, `cleanup_vector_base` também vivem ali).

2. **Novo método auxiliar `VectorAdminRepository._count_ingestion_logs(original_file_id)`**, não-destrutivo (espelha `_best_effort_delete_ingestion_logs`, mas com `SELECT ... count='exact'` em vez de `DELETE`):
   ```python
   def _count_ingestion_logs(self, original_file_id: str) -> int:
       total = 0
       for table_name in ['ingestion_logs', 'rag_ingestion_logs']:
           try:
               response = (
                   supabase_admin.table(table_name)
                   .select('id', count='exact')
                   .eq('original_file_id', original_file_id)
                   .execute()
               )
               total += response.count or 0
           except Exception as e:
               self.logger.warning(f'Falha ao contar logs da tabela {table_name}: {e}')
       return total
   ```
   - Usa o parâmetro `count='exact'` do PostgREST/supabase-py para obter a contagem exata sem baixar as linhas — mais eficiente que buscar e contar em Python.

3. **`VectorAdminService.cleanup`**: o branch `if confirmation_phrase:` (bool True) passa a chamar `self._call_repo_method(['preview_cleanup'], )` em vez de retornar o dicionário fixo.

4. **`VectorAdminRepository.cleanup_vector_base`** (execução real): adicionar `'dry_run': False` ao dicionário de retorno, sem alterar o restante da lógica.

5. **`CleanupVectorBaseResponse`**: adicionar `dry_run: bool = False`. **`_normalize_cleanup_response`** em `main.py`: adicionar `'dry_run': result.get('dry_run', False)` ao dicionário normalizado (em ambos os branches, `isinstance(result, dict)` e o `else`).

## Risks / Trade-offs

- **[Risco] `_count_ingestion_logs` roda uma query por arquivo por tabela (2 tabelas × N arquivos)** → aceitável para a escala atual (poucas dezenas de arquivos); se a base crescer muito, pode ser otimizado para uma única query com `IN (...)` no futuro — fora de escopo agora.
- **[Trade-off] O campo `dry_run` é nulo/ausente em respostas antigas em cache no frontend** → mitigado por ter `default=False` no schema, então clientes que não conhecem o campo simplesmente o ignoram; nenhum client quebra.
- **[Risco] Divergência entre o que `preview_cleanup` conta e o que `cleanup_vector_base` realmente apaga** → mitigado por ambos reaproveitarem exatamente `list_files()` como fonte da verdade para "quais arquivos existem"; a única diferença é que um conta e o outro deleta.
