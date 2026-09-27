# CAMINHO: backend/app/services/fish_analysis_job_service.py
"""
FishAnalysisJobService — estado durável dos jobs assíncronos de análise de
imagens (par lateral + superior).

O processamento em si (download, rembg, métricas, criação da análise)
continua rodando em background no mesmo processo que criou o job — este
serviço só lê/escreve o estado em `fish_analysis_jobs` (Postgres via
Supabase, RLS por user_id). Isso é necessário porque o backend roda com
múltiplos workers uvicorn (--workers 4): o worker que atende o GET de
status pode não ser o que está executando o processamento, então o estado
não pode viver só em memória.

Ver openspec/changes/async-fish-analysis-processing/design.md.

Pré-requisito (Supabase Dashboard): tabela `fish_analysis_jobs` criada via
backend/docs/setup_fish_images.sql.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.database import get_user_scoped_client

logger = logging.getLogger(__name__)

TABLE_NAME = "fish_analysis_jobs"
ACTIVE_STATUSES = ("queued", "processing")

# Job em queued/processing por mais que isso é tratado como órfão (ex.:
# worker morreu no meio do processamento — já ocorreu crash nativo do
# onnxruntime, sem traceback Python capturável) e marcado como 'error' em
# vez de ficar preso indefinidamente.
JOB_STALE_AFTER_SECONDS = int(os.getenv("JOB_STALE_AFTER_SECONDS", "300"))

_ORPHAN_ERROR_MESSAGE = "Processamento interrompido. Tente novamente."


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class FishAnalysisJobService:
    # ── helpers ───────────────────────────────────────────────────────────────

    def is_stale(self, row: Dict[str, Any]) -> bool:
        if row.get("status") not in ACTIVE_STATUSES:
            return False
        reference = _parse_ts(row.get("started_at")) or _parse_ts(row.get("created_at"))
        if reference is None:
            return False
        age_seconds = (datetime.now(timezone.utc) - reference).total_seconds()
        return age_seconds > JOB_STALE_AFTER_SECONDS

    def _mark_stale_as_error(self, user_client, row: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        update = {"status": "error", "error": _ORPHAN_ERROR_MESSAGE, "finished_at": now}
        result = user_client.table(TABLE_NAME).update(update).eq("id", row["id"]).execute()
        logger.warning("[fish_analysis_job] job obsoleto marcado como error id=%s", row["id"])
        return result.data[0] if result.data else {**row, **update}

    # ── operações públicas ────────────────────────────────────────────────────

    def find_active_job(
        self, user_id: str, access_token: str, lateral_id: str, superior_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Job não obsoleto já existente para o mesmo par de imagens do
        mesmo usuário — usado para a idempotência de reenvio/duplo clique.
        Jobs obsoletos encontrados no caminho são marcados 'error'."""
        user_client = get_user_scoped_client(access_token)
        result = (
            user_client.table(TABLE_NAME)
            .select("*")
            .eq("user_id", user_id)
            .eq("lateral_id", lateral_id)
            .eq("superior_id", superior_id)
            .in_("status", list(ACTIVE_STATUSES))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        if self.is_stale(row):
            self._mark_stale_as_error(user_client, row)
            return None
        return row

    def create_job(
        self,
        user_id: str,
        access_token: str,
        lateral_id: str,
        superior_id: str,
        fator_lateral: Optional[float],
        fator_superior: Optional[float],
        peso_g: Optional[float],
    ) -> Dict[str, Any]:
        user_client = get_user_scoped_client(access_token)
        row = {
            "user_id": user_id,
            "lateral_id": lateral_id,
            "superior_id": superior_id,
            "params": {
                "fator_lateral": fator_lateral,
                "fator_superior": fator_superior,
                "peso_g": peso_g,
            },
            "status": "queued",
        }
        result = user_client.table(TABLE_NAME).insert(row).execute()
        if not result.data:
            raise RuntimeError("Falha ao criar job de análise")
        job = result.data[0]
        logger.info("[fish_analysis_job] job criado id=%s", job["id"])
        return job

    def get_job(self, job_id: str, user_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """Retorna o job se existir e pertencer a `user_id`. RLS já filtra
        por auth.uid(), mas a posse é reconfirmada em Python como defesa em
        profundidade (mesmo padrão de fish_image_service)."""
        user_client = get_user_scoped_client(access_token)
        result = user_client.table(TABLE_NAME).select("*").eq("id", job_id).execute()
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        if row["user_id"] != user_id:
            return None
        if self.is_stale(row):
            row = self._mark_stale_as_error(user_client, row)
        return row

    def mark_processing(self, job_id: str, access_token: str) -> None:
        user_client = get_user_scoped_client(access_token)
        now = datetime.now(timezone.utc).isoformat()
        user_client.table(TABLE_NAME).update(
            {"status": "processing", "started_at": now}
        ).eq("id", job_id).execute()

    def mark_done(
        self, job_id: str, access_token: str, analysis_id: str, result: Dict[str, Any],
    ) -> None:
        user_client = get_user_scoped_client(access_token)
        now = datetime.now(timezone.utc).isoformat()
        user_client.table(TABLE_NAME).update(
            {"status": "done", "analysis_id": analysis_id, "result": result, "finished_at": now}
        ).eq("id", job_id).execute()
        logger.info("[fish_analysis_job] job concluído id=%s analysis_id=%s", job_id, analysis_id)

    def mark_error(self, job_id: str, access_token: str, message: str) -> None:
        user_client = get_user_scoped_client(access_token)
        now = datetime.now(timezone.utc).isoformat()
        user_client.table(TABLE_NAME).update(
            {"status": "error", "error": message, "finished_at": now}
        ).eq("id", job_id).execute()


# ── Singleton ──────────────────────────────────────────────────────────────────
fish_analysis_job_service = FishAnalysisJobService()
