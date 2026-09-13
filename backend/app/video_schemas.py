# CAMINHO: backend/app/video_schemas.py
"""
Schemas Pydantic para a funcionalidade de Biblioteca de Vídeos.

Rotas que consomem estes schemas:
  POST   /videos/upload         → VideoUploadResponse   (admin)
  GET    /videos                → VideoListResponse     (usuário autenticado)
  DELETE /videos/{video_id}     → VideoDeleteResponse   (admin)
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class VideoItem(BaseModel):
    """Representa um vídeo na listagem — inclui signed URL de 24h."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    title: str
    description: Optional[str] = None
    category: str = "geral"
    filename: str
    file_size: Optional[int] = None   # bytes
    url: str                          # signed URL válida por 24h
    created_at: str
    uploaded_by: Optional[str] = None


class VideoListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    items: List[VideoItem]
    total: int


class VideoUploadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    title: str
    category: str
    filename: str
    storage_path: str
    file_size: int
    status: str
    message: str


class VideoDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    status: str
    message: str
    storage_deleted: bool = False
