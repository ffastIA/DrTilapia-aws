-- ============================================================
-- DrTilapIA — Setup: Cadastro de Perfil do Usuário (Meu Perfil)
-- Execute no Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- ── Tabela user_profiles ─────────────────────────────────────
-- 1:1 com public.users (PK = FK = user_id). O e-mail NÃO é
-- duplicado aqui — é sempre lido de users.email (ver design.md,
-- decisão 3). sequential_id é gerado pelo Postgres e serve como
-- código de cadastro legível, distinto do uuid.
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id                 UUID        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sequential_id           INTEGER     GENERATED ALWAYS AS IDENTITY UNIQUE,

    -- Dados pessoais
    full_name               TEXT        NOT NULL,
    phone                    TEXT        NOT NULL,
    instagram                TEXT,
    linkedin                 TEXT,

    -- Empresa / produção
    company_name             TEXT,
    cnpj                      TEXT,
    farming_type              TEXT        NOT NULL CHECK (farming_type IN ('piscicultura', 'carcinicultura')),
    annual_production_tons    NUMERIC(10,1) NOT NULL CHECK (annual_production_tons >= 0),
    contact_role               TEXT,
    water_surface_area_ha      NUMERIC(10,2),
    tank_count                  INTEGER,
    predominant_species          TEXT,
    company_website               TEXT,

    -- Endereço (todos opcionais)
    address_street                 TEXT,
    address_number                  TEXT,
    address_complement               TEXT,
    address_zip_code                  TEXT,
    address_city                       TEXT,
    address_state                       TEXT CHECK (address_state IN (
        'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
        'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'
    )),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Trigger: manter updated_at em dia ────────────────────────
CREATE OR REPLACE FUNCTION set_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION set_user_profiles_updated_at();

-- ── RLS ───────────────────────────────────────────────────────
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

-- Sem policy de DELETE: o usuário nunca apaga o próprio perfil,
-- só substitui via upsert (ver design.md, decisão 4).

GRANT ALL ON public.user_profiles TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
