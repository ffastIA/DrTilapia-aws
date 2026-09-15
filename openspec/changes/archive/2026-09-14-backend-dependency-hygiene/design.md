## Context

`backend/requirements.txt` (estado atual confirmado nesta sessão):
```
bcrypt==4.1.2
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
sqlalchemy==2.0.29
sqlmodel>=0.0.22
```
Nenhuma dessas cinco linhas tem uso confirmado no código: `bcrypt`/`jose` não aparecem em nenhum `import` de `backend/app`; `sqlalchemy`/`sqlmodel` também não — a camada de dados é inteiramente `supabase-py` (`backend/app/database.py`).

## Goals / Non-Goals

**Goals:**
- Zero dependência com CVE conhecida sem correção disponível na versão pinada.
- Zero dependência listada sem uso real no código.

**Non-Goals:**
- Não introduzir ferramenta de scanning automático de dependências (ex.: `pip-audit`/Dependabot) nesta mudança — pode ser um item futuro separado, mas não é o escopo aqui.
- Não reavaliar todas as outras dependências com `>=` (sem teto de versão) quanto a atualizações — fora de escopo; esta mudança é focada nos itens já identificados pela auditoria.

## Decisions

1. **Remover em vez de apenas atualizar `jose`/`bcrypt`/`sqlalchemy`/`sqlmodel`**: como não há nenhum uso real, atualizar a versão pinada não reduziria risco nem traria benefício — a única ação que elimina a superfície de CVE é a remoção.
2. **Atualizar (não remover) `python-multipart`**: esta, ao contrário das outras quatro, é uma dependência real (usada implicitamente pelo FastAPI para parsing de `multipart/form-data` em todo upload) — a correção correta é o bump de versão, não a remoção.
3. **Confirmar ausência de uso antes de remover**: a decisão de remoção depende inteiramente da busca por `import` já realizada; se uma revisão futura encontrar um uso indireto não capturado pela busca textual (ex.: um plugin/hook que importa dinamicamente), a remoção deve ser revertida para aquele pacote especificamente.

## Risks / Trade-offs

- **[Risco baixo]** Se algum código gerado dinamicamente ou script fora de `backend/app/` (ex.: `create_user.py`, `criar_admin.py` na raiz de `backend/`) importar `jose`/`bcrypt`, a remoção quebraria esse script — mitigado verificando esses arquivos soltos também antes de remover (não apenas `backend/app/`).
- **[Trade-off]** Bump de `python-multipart` para `>=0.0.18` pode trazer mudanças de comportamento de parsing entre versões — mitigado rodando a suíte de testes de upload existente após a atualização.
