# CAMINHO: backend/app/services/fish_image_service.py
"""
FishImageService — gerencia o ciclo de vida de imagens de peixes.

Responsabilidades:
  - upload_image   : salva imagem no bucket 'fish-images' e cria registro na tabela
  - list_images    : lista imagens do usuário com signed URLs e filtros opcionais
  - list_analyses  : lista análises do usuário com filtros opcionais
  - delete_image   : remove imagem do Storage e da tabela fish_images
  - delete_analysis: remove análise e ambas as imagens do Storage + tabelas

Pré-requisitos (Supabase Dashboard):
  1. Bucket "fish-images" criado como PRIVADO
  2. Tabelas fish_analyses e fish_images criadas via setup_fish_images.sql
"""

import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.database import supabase_admin, get_user_scoped_client

logger = logging.getLogger(__name__)

BUCKET_NAME = "fish-images"
SIGNED_URL_EXPIRY = 3_600  # 1 hora — suficiente para sessão de análise

ALLOWED_EXTENSIONS: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


class FishImageService:
    def __init__(self) -> None:
        # Usado só para Storage (não há RLS em storage.objects para este bucket
        # hoje). Leituras/escritas nas tabelas fish_images/fish_analyses usam um
        # cliente escopado ao usuário chamador (ver get_user_scoped_client),
        # para que as policies de RLS de posse já existentes sejam aplicadas.
        self.supabase_admin = supabase_admin
        self.bucket = BUCKET_NAME

    # ── helpers ───────────────────────────────────────────────────────────────

    def _content_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return ALLOWED_EXTENSIONS.get(ext, "image/jpeg")

    def _make_storage_path(self, user_id: str, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return f"{user_id}/{uuid.uuid4().hex}{ext}"

    def _signed_url(self, storage_path: str) -> str:
        try:
            resp = self.supabase_admin.storage.from_(self.bucket).create_signed_url(
                storage_path, SIGNED_URL_EXPIRY
            )
            if isinstance(resp, dict):
                return (
                    resp.get("signedURL")
                    or resp.get("signedUrl")
                    or resp.get("signed_url")
                    or ""
                )
            return getattr(resp, "signed_url", "") or ""
        except Exception as exc:
            logger.warning("[fish_service] signed_url falhou para %s: %s", storage_path, exc)
            return ""

    def _row_to_image(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "analysis_id": row.get("analysis_id"),
            "user_id": row["user_id"],
            "tag": row["tag"],
            "filename": row["filename"],
            "storage_path": row["storage_path"],
            "uploaded_at": str(row["uploaded_at"]),
            "url": self._signed_url(row["storage_path"]),
            "fator_conversao": row.get("fator_conversao"),
            "bbox_width_px": row.get("bbox_width_px"),
            "bbox_height_px": row.get("bbox_height_px"),
            "bbox_width_cm": row.get("bbox_width_cm"),
            "bbox_height_cm": row.get("bbox_height_cm"),
            "mask_area_px": row.get("mask_area_px"),
            "mask_area_cm2": row.get("mask_area_cm2"),
            "peso_g": row.get("peso_g"),
            "processing_status": row.get("processing_status", "pending"),
            "processing_error": row.get("processing_error"),
            "processed_at": str(row["processed_at"]) if row.get("processed_at") else None,
        }

    # ── operações públicas ────────────────────────────────────────────────────

    def upload_image(
        self,
        file_path: str,
        filename: str,
        tag: str,
        user_id: str,
        access_token: str,
        fator_conversao: Optional[float] = None,
    ) -> Dict[str, Any]:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Formato '{ext}' não suportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        if tag not in ("lateral", "superior"):
            raise ValueError("tag deve ser 'lateral' ou 'superior'")

        storage_path = self._make_storage_path(user_id, filename)
        content_type = self._content_type(filename)

        logger.info("[fish_service] upload: '%s' tag=%s → %s", filename, tag, storage_path)

        with open(file_path, "rb") as f:
            self.supabase_admin.storage.from_(self.bucket).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": content_type},
            )

        row = {
            "user_id": user_id,
            "tag": tag,
            "filename": filename,
            "storage_path": storage_path,
            "fator_conversao": fator_conversao,
            "processing_status": "pending",
        }
        user_client = get_user_scoped_client(access_token)
        result = user_client.table("fish_images").insert(row).execute()

        if not result.data:
            self.supabase_admin.storage.from_(self.bucket).remove([storage_path])
            raise RuntimeError("Falha ao salvar metadados da imagem no banco")

        image_id = result.data[0]["id"]
        logger.info("[fish_service] imagem salva id=%s", image_id)
        return {
            "id": image_id,
            "tag": tag,
            "filename": filename,
            "storage_path": storage_path,
            "status": "success",
            "message": "Imagem enviada com sucesso",
        }

    def list_images(
        self,
        user_id: str,
        access_token: str,
        tag: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        user_client = get_user_scoped_client(access_token)
        query = (
            user_client.table("fish_images")
            .select("*")
            .eq("user_id", user_id)
            .order("uploaded_at", desc=True)
        )
        if tag:
            query = query.eq("tag", tag)
        if date_from:
            query = query.gte("uploaded_at", date_from)
        if date_to:
            query = query.lte("uploaded_at", date_to)

        result = query.execute()
        items = [self._row_to_image(r) for r in (result.data or [])]
        return {"items": items, "total": len(items)}

    def list_analyses(
        self,
        user_id: str,
        access_token: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kvol_min: Optional[float] = None,
        kvol_max: Optional[float] = None,
    ) -> Dict[str, Any]:
        user_client = get_user_scoped_client(access_token)
        query = (
            user_client.table("fish_analyses")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        if date_from:
            query = query.gte("created_at", date_from)
        if date_to:
            query = query.lte("created_at", date_to)
        if kvol_min is not None:
            query = query.gte("kvol", kvol_min)
        if kvol_max is not None:
            query = query.lte("kvol", kvol_max)

        result = query.execute()
        analyses = result.data or []

        items = []
        for a in analyses:
            # Buscar imagens associadas
            imgs_result = (
                user_client.table("fish_images")
                .select("*")
                .eq("analysis_id", a["id"])
                .execute()
            )
            lateral = next(
                (self._row_to_image(r) for r in (imgs_result.data or []) if r["tag"] == "lateral"),
                None,
            )
            superior = next(
                (self._row_to_image(r) for r in (imgs_result.data or []) if r["tag"] == "superior"),
                None,
            )
            items.append({
                "id": a["id"],
                "user_id": a["user_id"],
                "created_at": str(a["created_at"]),
                "peso_g": a.get("peso_g"),
                "kvol": a.get("kvol"),
                "comprimento_cm": a.get("comprimento_cm"),
                "altura_cm": a.get("altura_cm"),
                "largura_cm": a.get("largura_cm"),
                "lateral_image": lateral,
                "superior_image": superior,
            })

        return {"items": items, "total": len(items)}

    def delete_image(self, image_id: str, user_id: str, access_token: str) -> Dict[str, Any]:
        user_client = get_user_scoped_client(access_token)
        result = (
            user_client.table("fish_images")
            .select("id, storage_path, user_id")
            .eq("id", image_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Imagem '{image_id}' não encontrada")
        row = result.data[0]
        if row["user_id"] != user_id:
            raise PermissionError("Sem permissão para excluir esta imagem")

        storage_deleted = False
        try:
            self.supabase_admin.storage.from_(self.bucket).remove([row["storage_path"]])
            storage_deleted = True
        except Exception as exc:
            logger.warning("[fish_service] falha ao remover storage %s: %s", row["storage_path"], exc)

        user_client.table("fish_images").delete().eq("id", image_id).execute()
        logger.info("[fish_service] imagem removida id=%s", image_id)
        return {"id": image_id, "status": "success", "message": "Imagem removida", "storage_deleted": storage_deleted}

    def delete_analysis(self, analysis_id: str, user_id: str, access_token: str) -> Dict[str, Any]:
        user_client = get_user_scoped_client(access_token)
        result = (
            user_client.table("fish_analyses")
            .select("id, user_id")
            .eq("id", analysis_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Análise '{analysis_id}' não encontrada")
        if result.data[0]["user_id"] != user_id:
            raise PermissionError("Sem permissão para excluir esta análise")

        # Buscar e remover imagens associadas do Storage
        imgs = (
            user_client.table("fish_images")
            .select("id, storage_path")
            .eq("analysis_id", analysis_id)
            .execute()
        ).data or []

        paths = [img["storage_path"] for img in imgs]
        if paths:
            try:
                self.supabase_admin.storage.from_(self.bucket).remove(paths)
            except Exception as exc:
                logger.warning("[fish_service] falha ao remover storage da análise: %s", exc)

        # Cascade via FK remove fish_images automaticamente (ON DELETE SET NULL)
        # Deletamos manualmente para remover do storage antes
        for img in imgs:
            user_client.table("fish_images").delete().eq("id", img["id"]).execute()

        user_client.table("fish_analyses").delete().eq("id", analysis_id).execute()
        logger.info("[fish_service] análise removida id=%s", analysis_id)
        return {"id": analysis_id, "status": "success", "message": "Análise removida com sucesso"}

    def download_image_bytes(self, storage_path: str) -> bytes:
        """Faz download dos bytes da imagem do Supabase Storage para processamento."""
        resp = self.supabase_admin.storage.from_(self.bucket).download(storage_path)
        if isinstance(resp, (bytes, bytearray)):
            return bytes(resp)
        raise RuntimeError(f"Falha ao baixar imagem: {storage_path}")


# ── Singleton ──────────────────────────────────────────────────────────────────
fish_image_service = FishImageService()
