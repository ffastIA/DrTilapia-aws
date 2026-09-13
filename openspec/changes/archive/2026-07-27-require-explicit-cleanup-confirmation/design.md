## Context

Cadeia completa hoje, de request a exclusão real, para `POST /admin/vector-base/cleanup`:

1. `backend/app/vector_admin_schemas.py:49-63`:
```python
class CleanupVectorBaseRequest(BaseModel):
    confirmation_phrase: Optional[str] = None
    dry_run: Optional[bool] = None

    @model_validator(mode="after")
    def validate_fields(self):
        if not self.confirmation_phrase or self.confirmation_phrase.strip() == "":
            if self.dry_run is True:
                self.confirmation_phrase = "SIMULACAO"
            else:
                self.confirmation_phrase = "CONFIRMAR_LIMPEZA_TOTAL"   # ← auto-preenche a frase destrutiva
        if self.confirmation_phrase and self.confirmation_phrase.strip() == "CONFIRMADO":
            self.confirmation_phrase = "CONFIRMAR_LIMPEZA_TOTAL"
        return self
```
2. `backend/app/main.py:214-226` repassa `request.confirmation_phrase`/`request.dry_run` para `vector_admin_service.cleanup(...)`.
3. `backend/app/services/vector_admin_service.py:89-95`:
```python
def cleanup(self, confirmation_phrase: Union[str, bool] = True) -> Any:
    if isinstance(confirmation_phrase, bool):
        if confirmation_phrase:
            return self._call_repo_method(['preview_cleanup'])
        else:
            confirmation_phrase = 'CONFIRMAR_LIMPEZA_TOTAL'          # ← também sintetiza a partir de bool
    return self._call_repo_method(['cleanup', 'cleanup_vector_base', 'clear_vector_base'], confirmation_phrase)
```
4. `backend/app/vector_admin_repository.py:401-403` (`cleanup_vector_base`) só verifica `if confirmation_phrase != self.CONFIRMAR_LIMPEZA_TOTAL: raise ValueError(...)` — mas nunca recebe outra coisa, porque as duas camadas acima já garantem que a frase correta chega ali sempre que `dry_run` não é `True`.

O mesmo padrão de auto-preenchimento existe em `DeleteFileRequest.validate_fields` (`vector_admin_schemas.py:22-35`), mas para exclusão de arquivo individual **não existe conceito de dry-run** — o campo é só `confirmation_phrase`/`reason`/`hard_delete`/`delete_chunks`, sem `dry_run`:
```python
class DeleteFileRequest(BaseModel):
    confirmation_phrase: Optional[str] = None
    reason: Optional[str] = None
    hard_delete: bool = True
    delete_chunks: Optional[bool] = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.delete_chunks is not None and self.hard_delete is None:
            self.hard_delete = self.delete_chunks
        if not self.confirmation_phrase or self.confirmation_phrase.strip() == "" or self.confirmation_phrase.strip() == "CONFIRMADO":
            self.confirmation_phrase = "CONFIRMAR_EXCLUSAO"
        return self
```

Verificado no frontend: o fluxo de **limpeza total** (`frontend/lib/ragAdminApi.ts:233-234, 259`) já envia a frase explicitamente hoje (`confirmation_phrase: 'CONFIRMADO'` quando confirmado, `dry_run: true` quando simulando) — não precisa mudar. Mas o fluxo de **exclusão individual** (`frontend/hooks/useRagAdmin.ts:84`, `deleteRagDocument({ ids: [selectedItem.id], delete_chunks: true })`) **não envia `confirmation_phrase` nenhuma** — hoje ele só funciona porque o schema auto-preenche `"CONFIRMAR_EXCLUSAO"` a partir do campo vazio. Remover o auto-preenchimento sem atualizar essa chamada quebraria a exclusão individual pelo painel admin.

## Goals / Non-Goals

**Goals:**
- Um corpo de requisição vazio ou incompleto nunca resulta em execução destrutiva real.
- O padrão "ausência de confirmação = tratar como não confirmado" é aplicado de forma consistente em `CleanupVectorBaseRequest` e `DeleteFileRequest`.
- O fluxo já usado pelo frontend (simular → confirmar explicitamente) continua funcionando sem mudança de UI.

**Non-Goals:**
- Não mudar o valor da frase de confirmação em si (`CONFIRMAR_LIMPEZA_TOTAL`, `CONFIRMAR_EXCLUSAO`) — só a regra de quando ela é aplicada.
- Não adicionar autenticação/step adicional (2FA, etc.) ao fluxo de confirmação — fora de escopo desta correção pontual.
- Não mexer na normalização de compatibilidade `"CONFIRMADO"` → frase interna atual, que é o caminho usado pelo frontend hoje e continua correto (o valor não está vazio, então a lógica de auto-preenchimento nem é acionada para esse caso).

## Decisions

1. **`CleanupVectorBaseRequest.validate_fields`: quando `confirmation_phrase` vem vazio/ausente, tratar como dry-run (nunca como `CONFIRMAR_LIMPEZA_TOTAL`).** Como o cleanup já tem um modo seguro nativo (dry-run/preview), a ausência de confirmação simplesmente cai nesse modo — comportamento seguro por padrão, sem quebrar nenhum contrato de erro.
2. **`DeleteFileRequest.validate_fields`: quando `confirmation_phrase` vem vazio/ausente, `raise ValueError(...)` no próprio validador** (o Pydantic converte automaticamente em erro 422 pelo FastAPI), em vez de auto-preencher `"CONFIRMAR_EXCLUSAO"`. Diferente do cleanup, a exclusão de arquivo não tem um modo "seguro" equivalente para cair por padrão — a única opção segura é recusar a requisição e pedir a confirmação explícita.
   - Mantém a normalização de compatibilidade `"CONFIRMADO"` → `"CONFIRMAR_EXCLUSAO"` (o valor não está vazio nesse caso, então não aciona a nova regra de rejeição).
3. **Atualizar `frontend/hooks/useRagAdmin.ts:84`** para enviar `confirmation_phrase: 'CONFIRMADO'` explicitamente na chamada de exclusão individual, já que o auto-preenchimento que a sustentava está sendo removido.
4. **Remover a coerção `bool`→frase em `VectorAdminService.cleanup`/`delete_file`.** Esses métodos passam a exigir uma `str` de confirmação explícita do chamador (o `main.py` já só repassa `request.confirmation_phrase`, uma string); a sobrecarga que aceitava `bool` e sintetizava a frase é removida, eliminando de vez o caminho onde um valor não-string vira "confirmado" por acidente de tipo.
5. **`preview_cleanup()` continua acessível pelo caminho de dry-run já existente** (`dry_run=True` no request, ou ausência de `confirmation_phrase` após a decisão 1) — nenhuma mudança nessa parte, que já está correta (mudança anterior desta sessão, `add-real-cleanup-dry-run-preview`).

## Risks / Trade-offs

- **[Risco] Algum chamador direto da API (fora do frontend) que hoje depende do auto-preenchimento para "confirmar por omissão" para de funcionar** → aceitável e intencional: essa dependência implícita é exatamente o comportamento perigoso que está sendo removido. Nenhum uso legítimo do fluxo via frontend é afetado (confirmado acima).
- **[Trade-off] Não adiciona uma segunda camada de confirmação (ex.: exigir reautenticação) para a ação mais destrutiva do sistema** — fora de escopo; pode ser proposto como melhoria futura separada.
