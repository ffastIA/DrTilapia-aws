-- ============================================================
-- DrTilapIA — Setup: Análise de Imagens por IA
-- Execute no Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- ── Tabela fish_analyses ─────────────────────────────────────
-- Agrupa um par de imagens (lateral + superior) de uma sessão
-- e armazena as métricas consolidadas da análise.
CREATE TABLE IF NOT EXISTS fish_analyses (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    peso_g         NUMERIC,
    kvol           NUMERIC,
    comprimento_cm NUMERIC,
    altura_cm      NUMERIC,
    largura_cm     NUMERIC
);

ALTER TABLE fish_analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "fish_analyses_select_own"
  ON fish_analyses FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_analyses_insert_own"
  ON fish_analyses FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "fish_analyses_update_own"
  ON fish_analyses FOR UPDATE TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_analyses_delete_own"
  ON fish_analyses FOR DELETE TO authenticated
  USING (user_id = auth.uid());

GRANT ALL  ON public.fish_analyses TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fish_analyses TO authenticated;


-- ── Tabela fish_images ───────────────────────────────────────
-- Armazena cada imagem individual com suas métricas e status.
CREATE TABLE IF NOT EXISTS fish_images (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id       UUID        REFERENCES fish_analyses(id) ON DELETE SET NULL,
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag               TEXT        NOT NULL CHECK (tag IN ('lateral', 'superior')),
    filename          TEXT        NOT NULL,
    storage_path      TEXT        NOT NULL,
    uploaded_at       TIMESTAMPTZ DEFAULT NOW(),
    fator_conversao   NUMERIC,          -- px/cm (manual ou detectado via ArUco)
    bbox_width_px     NUMERIC,
    bbox_height_px    NUMERIC,
    bbox_width_cm     NUMERIC,
    bbox_height_cm    NUMERIC,
    mask_area_px      NUMERIC,
    mask_area_cm2     NUMERIC,
    peso_g            NUMERIC,          -- redundante p/ facilitar dashboards por imagem
    processing_status TEXT        DEFAULT 'pending'
                                  CHECK (processing_status IN ('pending','processing','done','error')),
    processing_error  TEXT,
    processed_at      TIMESTAMPTZ
);

ALTER TABLE fish_images ENABLE ROW LEVEL SECURITY;

CREATE POLICY "fish_images_select_own"
  ON fish_images FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_images_insert_own"
  ON fish_images FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "fish_images_update_own"
  ON fish_images FOR UPDATE TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_images_delete_own"
  ON fish_images FOR DELETE TO authenticated
  USING (user_id = auth.uid());

GRANT ALL  ON public.fish_images TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fish_images TO authenticated;


-- ── Tabela fish_analysis_jobs ─────────────────────────────────
-- Estado durável do processamento assíncrono de um par de imagens
-- (lateral + superior). POST /fish/analyses/process cria uma linha aqui e
-- responde de imediato; o processamento roda em background e atualiza o
-- status/resultado, consultado via GET /fish/analyses/jobs/{id}. Necessária
-- porque o backend roda com múltiplos workers uvicorn — sem isso, o worker
-- que atende o GET pode não ser o que executou o processamento.
-- Ver openspec/changes/async-fish-analysis-processing/design.md.
CREATE TABLE IF NOT EXISTS fish_analysis_jobs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lateral_id  UUID        NOT NULL REFERENCES fish_images(id) ON DELETE CASCADE,
    superior_id UUID        NOT NULL REFERENCES fish_images(id) ON DELETE CASCADE,
    params      JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- fator_lateral, fator_superior, peso_g
    status      TEXT        NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','processing','done','error')),
    result      JSONB,        -- ProcessResponse serializado, quando status = 'done'
    error       TEXT,         -- mensagem sanitizada ao cliente, quando status = 'error'
    analysis_id UUID        REFERENCES fish_analyses(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

ALTER TABLE fish_analysis_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "fish_analysis_jobs_select_own"
  ON fish_analysis_jobs FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_analysis_jobs_insert_own"
  ON fish_analysis_jobs FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "fish_analysis_jobs_update_own"
  ON fish_analysis_jobs FOR UPDATE TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "fish_analysis_jobs_delete_own"
  ON fish_analysis_jobs FOR DELETE TO authenticated
  USING (user_id = auth.uid());

GRANT ALL  ON public.fish_analysis_jobs TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fish_analysis_jobs TO authenticated;

-- Acelera a checagem de idempotência (já existe job ativo para este par de
-- imagens deste usuário?) sem escanear jobs concluídos/antigos.
CREATE INDEX IF NOT EXISTS fish_analysis_jobs_active_pair_idx
  ON fish_analysis_jobs (user_id, lateral_id, superior_id)
  WHERE status IN ('queued', 'processing');
