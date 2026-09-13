# CAMINHO: backend/app/services/video_service.py
"""
VideoService — gerencia o ciclo de vida de vídeos na plataforma DrTilapIA.

Responsabilidades:
  - upload_video   : faz upload para o bucket Supabase Storage "videos"
                     e persiste metadados na tabela pública "videos"
  - list_videos    : lista todos os registros com signed URLs de 24 h
  - delete_video   : remove do Storage e da tabela

Pré-requisitos (Supabase Dashboard):
  1. Bucket "videos" criado como PRIVADO
  2. Tabela "videos" criada com o seguinte SQL:

     CREATE TABLE videos (
         id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
         title        TEXT        NOT NULL,
         description  TEXT,
         category     TEXT        DEFAULT 'geral',
         filename     TEXT        NOT NULL,
         storage_path TEXT        NOT NULL,
         file_size    BIGINT,
         uploaded_by  UUID        REFERENCES users(id),
         created_at   TIMESTAMPTZ DEFAULT NOW(),
         updated_at   TIMESTAMPTZ DEFAULT NOW()
     );

     ALTER TABLE videos ENABLE ROW LEVEL SECURITY;

     -- Leitura: qualquer usuário autenticado
     CREATE POLICY "videos_select_authenticated"
       ON videos FOR SELECT TO authenticated USING (true);

     -- Inserção e exclusão: somente admins
     CREATE POLICY "videos_insert_admin"
       ON videos FOR INSERT TO authenticated
       WITH CHECK (
           (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
       );

     CREATE POLICY "videos_delete_admin"
       ON videos FOR DELETE TO authenticated
       USING (
           (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
       );
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Any

from app.database import supabase_admin

logger = logging.getLogger(__name__)

# ── Configurações ─────────────────────────────────────────────────────────────

BUCKET_NAME = "videos"

# Signed URL válida por 24 horas — suficiente para toda uma sessão de visualização
SIGNED_URL_EXPIRY_SECONDS = 86_400

# Extensões aceitas → content-type correto para o Storage
ALLOWED_EXTENSIONS: Dict[str, str] = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


# ── Service ───────────────────────────────────────────────────────────────────

class VideoService:
    """Serviço de vídeos — wrapper sobre Supabase Storage + tabela 'videos'."""

    def __init__(self) -> None:
        self.supabase = supabase_admin
        self.bucket = BUCKET_NAME

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _content_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return ALLOWED_EXTENSIONS.get(ext, "video/mp4")

    def _make_storage_path(self, filename: str) -> str:
        """Gera um caminho único no bucket para evitar colisão de nomes."""
        ext = Path(filename).suffix.lower()
        return f"{uuid.uuid4().hex}{ext}"

    def _extract_signed_url(self, signed_response: Any) -> str:
        """Extrai a URL da resposta de create_signed_url (compatível com supabase-py v1 e v2)."""
        if isinstance(signed_response, dict):
            return (
                signed_response.get("signedURL")
                or signed_response.get("signedUrl")
                or signed_response.get("signed_url")
                or ""
            )
        # supabase-py v2 pode retornar objeto com atributo .signed_url
        return getattr(signed_response, "signed_url", "") or ""

    # ── Operações públicas ────────────────────────────────────────────────────

    def upload_video(
        self,
        file_path: str,
        filename: str,
        title: str,
        description: str,
        category: str,
        uploader_id: str,
    ) -> Dict[str, Any]:
        """
        Faz upload do vídeo para o Supabase Storage e salva metadados.

        Args:
            file_path    : caminho do arquivo temporário no servidor
            filename     : nome original do arquivo (ex: "tutorial_tilap.mp4")
            title        : título exibido na biblioteca
            description  : descrição opcional
            category     : categoria (ex: "nutrição", "genética", "geral")
            uploader_id  : UUID do usuário admin que faz o upload

        Returns:
            dict com id, title, storage_path, file_size, status e message

        Raises:
            ValueError  : extensão não permitida
            RuntimeError: falha ao salvar metadados (arquivo removido do Storage)
        """
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Formato '{ext}' não suportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        file_size = os.path.getsize(file_path)
        storage_path = self._make_storage_path(filename)
        content_type = self._content_type(filename)

        logger.info(
            "[video_service] upload iniciado: '%s' → %s (%d bytes)",
            filename, storage_path, file_size,
        )

        # ── 1. Upload para Supabase Storage ───────────────────────────────────
        with open(file_path, "rb") as f:
            self.supabase.storage.from_(self.bucket).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": content_type},
            )

        logger.info("[video_service] storage OK: %s", storage_path)

        # ── 2. Persistir metadados na tabela videos ────────────────────────────
        row = {
            "title": title.strip(),
            "description": description.strip() if description else None,
            "category": category.strip() if category else "geral",
            "filename": filename,
            "storage_path": storage_path,
            "file_size": file_size,
            "uploaded_by": uploader_id,
        }

        result = self.supabase.table("videos").insert(row).execute()

        if not result.data:
            # Limpar o arquivo do Storage para não deixar órfão
            try:
                self.supabase.storage.from_(self.bucket).remove([storage_path])
                logger.warning("[video_service] arquivo órfão removido do storage após falha no DB")
            except Exception as cleanup_exc:
                logger.error("[video_service] falha na limpeza do storage: %s", cleanup_exc)
            raise RuntimeError("Falha ao salvar metadados do vídeo no banco de dados")

        video_id = result.data[0]["id"]
        logger.info("[video_service] metadados salvos id=%s title='%s'", video_id, title)

        return {
            "id": video_id,
            "title": title,
            "category": category or "geral",
            "filename": filename,
            "storage_path": storage_path,
            "file_size": file_size,
            "status": "success",
            "message": "Vídeo enviado com sucesso",
        }

    def list_videos(self) -> Dict[str, Any]:
        """
        Retorna todos os vídeos com signed URLs válidas por 24 h.

        Ordered by: created_at DESC (mais recentes primeiro).
        """
        result = (
            self.supabase.table("videos")
            .select(
                "id, title, description, category, filename, "
                "file_size, storage_path, created_at, uploaded_by"
            )
            .order("created_at", desc=True)
            .execute()
        )

        items = []
        for row in result.data or []:
            try:
                signed = self.supabase.storage.from_(self.bucket).create_signed_url(
                    row["storage_path"],
                    SIGNED_URL_EXPIRY_SECONDS,
                )
                url = self._extract_signed_url(signed)
            except Exception as exc:
                logger.warning(
                    "[video_service] falha ao gerar signed URL para %s: %s",
                    row["storage_path"], exc,
                )
                url = ""

            items.append({
                "id": row["id"],
                "title": row["title"],
                "description": row.get("description"),
                "category": row.get("category", "geral"),
                "filename": row["filename"],
                "file_size": row.get("file_size"),
                "url": url,
                "created_at": str(row["created_at"]),
                "uploaded_by": row.get("uploaded_by"),
            })

        logger.info("[video_service] list_videos → %d itens", len(items))
        return {"items": items, "total": len(items)}

    def delete_video(self, video_id: str) -> Dict[str, Any]:
        """
        Remove o vídeo do Storage e da tabela.

        A deleção do DB ocorre mesmo se a remoção do Storage falhar,
        para evitar registros zumbis. A falha de storage é logada como warning.

        Raises:
            ValueError: vídeo não encontrado
        """
        # Buscar storage_path antes de deletar
        result = (
            self.supabase.table("videos")
            .select("id, storage_path, filename")
            .eq("id", video_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Vídeo '{video_id}' não encontrado")

        storage_path = result.data[0]["storage_path"]
        filename = result.data[0]["filename"]
        storage_deleted = False

        # ── 1. Remover do Storage ──────────────────────────────────────────────
        try:
            self.supabase.storage.from_(self.bucket).remove([storage_path])
            storage_deleted = True
            logger.info("[video_service] storage removido: %s", storage_path)
        except Exception as exc:
            logger.warning(
                "[video_service] falha ao remover '%s' do storage: %s",
                storage_path, exc,
            )

        # ── 2. Remover da tabela ───────────────────────────────────────────────
        self.supabase.table("videos").delete().eq("id", video_id).execute()
        logger.info("[video_service] registro removido da tabela: id=%s filename='%s'", video_id, filename)

        return {
            "id": video_id,
            "status": "success",
            "message": "Vídeo removido com sucesso",
            "storage_deleted": storage_deleted,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
video_service = VideoService()
