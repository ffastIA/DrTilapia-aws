## Context

`public.users` guarda hoje só `id` (= `auth.uid()`), `email` e `role` — o mínimo para autenticação. Não existe nenhum dado de perfil (pessoa, empresa, endereço). O padrão de dados já estabelecido no projeto (`fish_analyses`, `fish_images`, ver `backend/docs/setup_fish_images.sql`) é: tabela própria com `user_id UUID REFERENCES users(id)`, RLS self-owned (`select/insert/update/delete` restritos a `user_id = auth.uid()`), um `Service` em `backend/app/services/`, e acesso via `get_user_scoped_client(access_token)` para que a RLS do próprio usuário valha (nunca `supabase_admin` para dados de posse do usuário).

## Goals / Non-Goals

**Goals:**
- Um cadastro de perfil (`user_profiles`) 1:1 com `users`, editável livremente pelo dono.
- Um identificador sequencial único por usuário, gerado pelo banco, independente da PK (uuid).
- Validação dupla (frontend + backend) dos campos obrigatórios.
- Schema com espaço para os campos sugeridos (empresa, endereço) sem forçar preenchimento agora.

**Non-Goals:**
- Não implementa o gate de onboarding (redirecionamento no 1º acesso, bloqueio de navegação, logout ao abandonar) — isso é `add-profile-onboarding-gate`.
- Não substitui email por nome no header — idem, fica na change de onboarding.
- Não valida CNPJ/CEP contra serviços externos (Receita/Correios) — validação é só de formato (regex), sem chamada de rede.
- Não versiona histórico de alterações do perfil (sem auditoria/log de mudanças nesta fase).

## Decisions

### 1. Tabela separada `user_profiles`, não colunas em `users`
`users` é a tabela de identidade/autorização (id, email, role) usada pelo middleware e pelo `get_current_user` em todo request autenticado. Perfil é um bloco de dados maior e opcional em sua maior parte. Separar evita inflar o hot path de auth com colunas nulas na maioria dos requests, e mantém `users` estável (spec `user-signup` já depende do shape atual). `user_profiles.user_id` é PK e FK para `users(id) ON DELETE CASCADE` — reforça o 1:1 sem precisar de UNIQUE adicional.

Alternativa considerada: adicionar colunas em `users`. Rejeitada — misturaria concerns de auth e perfil, e toda leitura de `users` (login, middleware admin) passaria a carregar campos irrelevantes.

### 2. `sequential_id` via `GENERATED ALWAYS AS IDENTITY`
Requisito explícito do usuário: "identificador sequencial no banco de dados que seja único por usuário", distinto do `id` (uuid, não sequencial/não legível). Implementado como `sequential_id INTEGER GENERATED ALWAYS AS IDENTITY UNIQUE` — o Postgres garante unicidade e monotonicidade sem lógica de aplicação (evita race condition de "pegar o MAX+1"). Não é a PK (a PK continua sendo `user_id`, que é o que já flui por todo o sistema via `auth.uid()`); serve como código de cadastro legível (ex.: "Cadastro #00042") exibível na própria página de perfil.

Alternativa considerada: sequência formatada por trigger (`CADASTRO-000042`). Rejeitada por complexidade desnecessária agora — o inteiro puro atende ao requisito; formatação de exibição pode ficar no frontend se necessário no futuro.

### 3. Email do perfil é somente-leitura, espelhado de `users.email`
O requisito pede "email" como campo obrigatório do cadastro. Mas o email de login já existe em `users.email` e é a fonte de verdade para autenticação/RLS. Duplicar como campo editável independente criaria dessincronia (login usa um email, perfil mostra outro). Decisão: `user_profiles` não guarda email próprio; o endpoint `GET /profile` retorna `email` lido de `users.email` (join), e o formulário exibe esse campo desabilitado/read-only com nota "para alterar o email de login, use as configurações de conta". Isso satisfaz "obrigatório e sempre preenchido" (é sempre o email de login) sem introduzir uma segunda fonte de verdade.

### 4. RLS self-owned, idêntica ao padrão `fish_*`
```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id           UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sequential_id      INTEGER GENERATED ALWAYS AS IDENTITY UNIQUE,
    full_name          TEXT NOT NULL,
    phone              TEXT NOT NULL,
    instagram          TEXT,
    linkedin           TEXT,
    company_name       TEXT,
    cnpj               TEXT,
    farming_type       TEXT NOT NULL CHECK (farming_type IN ('piscicultura', 'carcinicultura')),
    annual_production_tons NUMERIC(10,1) NOT NULL CHECK (annual_production_tons >= 0),
    contact_role       TEXT,
    water_surface_area_ha NUMERIC(10,2),
    tank_count         INTEGER,
    predominant_species TEXT,
    company_website    TEXT,
    address_street      TEXT,
    address_number       TEXT,
    address_complement   TEXT,
    address_zip_code     TEXT,
    address_city         TEXT,
    address_state        TEXT CHECK (address_state IN (
        'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
        'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_profiles_select_own"
  ON user_profiles FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "user_profiles_insert_own"
  ON user_profiles FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "user_profiles_update_own"
  ON user_profiles FOR UPDATE TO authenticated
  USING (user_id = auth.uid());

GRANT ALL ON public.user_profiles TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
-- Sem DELETE: o perfil é substituído via upsert, nunca apagado pelo próprio usuário.
```
`updated_at` é mantido via trigger `BEFORE UPDATE` (mesmo padrão simples de `NOW()`, sem extensão adicional).

### 5. Campos extras sugeridos (todos opcionais)
- `contact_role` (cargo/função do contato): útil para priorizar atendimento (ex. "sócio-proprietário" vs "técnico").
- `water_surface_area_ha` (área de lâmina d'água em hectares) e `tank_count` (nº de tanques/viveiros): dimensionam o porte da operação além da produção anual — dois produtores com a mesma tonelagem podem ter estruturas muito diferentes.
- `predominant_species`: relevante porque "piscicultura" cobre múltiplas espécies (tilápia, tambaqui, etc.) e isso pode direcionar conteúdo/recomendações do RAG no futuro.
- `company_website`: canal adicional de contato/qualificação comercial, baixo custo de coleta.

### 6. Endpoint único de upsert (`PUT /profile`), sem `POST` separado
Como o requisito é "pode alterar a qualquer momento" e o 1:1 já é garantido pela PK, criar/atualizar é a mesma operação (`upsert` no Postgres). Evita a ambiguidade de UI entre "primeiro cadastro" vs "edição" no backend — essa distinção (redirecionar no primeiro acesso) é tratada inteiramente no frontend/onboarding gate, não no contrato da API.

### 7. Validação de obrigatórios no backend via Pydantic, não via NOT NULL cru
As colunas `full_name`, `phone`, `farming_type`, `annual_production_tons` são `NOT NULL` no banco (defesa em profundidade), mas a validação primária de "campos obrigatórios preenchidos" e suas mensagens de erro ficam no schema Pydantic do endpoint (`backend/app/profile_schemas.py`), para devolver 422 com mensagens claras por campo em vez de um erro genérico de constraint do Postgres.

## Risks / Trade-offs

- [Divergência entre `users.email` e o email realmente usado para contato comercial] → Mitigado documentando no formulário que é o email de login; se no futuro for preciso um email de contato diferente, adicionar campo `contact_email` opcional é uma mudança aditiva, não breaking.
- [`sequential_id` do tipo IDENTITY cria "buracos" na sequência se um insert falhar/for revertido] → Aceitável: o requisito é unicidade e ordem, não contiguidade perfeita; é o mesmo comportamento de qualquer `SERIAL`/`IDENTITY` do Postgres.
- [CNPJ/CEP aceitos só com validação de formato, não de existência real] → Aceitável nesta fase (Non-Goal); documentar explicitamente para não gerar expectativa de verificação.
- [Dropdown de `farming_type` fixo em 2 valores via CHECK constraint] → Se surgir um terceiro tipo de criação no futuro, exige migration para alterar o CHECK; aceitável dado que os dois valores foram explicitamente pedidos pelo usuário.

## Migration Plan

1. Criar migration SQL (`backend/docs/setup_user_profiles.sql`, seguindo o padrão de `setup_fish_images.sql`) com a tabela, RLS, grants e trigger de `updated_at`.
2. Aplicar no Supabase (SQL Editor, mesmo fluxo manual já usado no projeto).
3. Deploy do backend (novas rotas) e frontend (nova página) — sem downtime, é aditivo (nenhuma tabela/rota existente é alterada).
4. Rollback: `DROP TABLE user_profiles` reverte integralmente (nenhuma outra tabela referencia `user_profiles`).

## Open Questions

- Nenhuma pendente para esta change — decisões acima cobrem todos os pontos levantados pelo usuário. A UX de "primeiro acesso"/bloqueio fica para `add-profile-onboarding-gate`.
