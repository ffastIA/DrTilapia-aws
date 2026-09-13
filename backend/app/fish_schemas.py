# CAMINHO: backend/app/fish_schemas.py

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ── Imagens individuais ────────────────────────────────────────────────────────

class FishImageItem(BaseModel):
    id: str
    analysis_id: Optional[str] = None
    user_id: str
    tag: str                          # 'lateral' | 'superior'
    filename: str
    storage_path: str
    uploaded_at: str
    url: Optional[str] = None         # signed URL gerada no momento da listagem
    fator_conversao: Optional[float] = None
    bbox_width_px: Optional[float] = None
    bbox_height_px: Optional[float] = None
    bbox_width_cm: Optional[float] = None
    bbox_height_cm: Optional[float] = None
    mask_area_px: Optional[float] = None
    mask_area_cm2: Optional[float] = None
    peso_g: Optional[float] = None
    processing_status: str = 'pending'
    processing_error: Optional[str] = None
    processed_at: Optional[str] = None


class FishImageListResponse(BaseModel):
    items: List[FishImageItem]
    total: int


class FishImageUploadResponse(BaseModel):
    id: str
    tag: str
    filename: str
    storage_path: str
    status: str
    message: str


class FishImageDeleteResponse(BaseModel):
    id: str
    status: str
    message: str
    storage_deleted: bool = False


# ── Análises (par lateral + superior) ─────────────────────────────────────────

class FishAnalysisItem(BaseModel):
    id: str
    user_id: str
    created_at: str
    peso_g: Optional[float] = None
    kvol: Optional[float] = None
    comprimento_cm: Optional[float] = None
    altura_cm: Optional[float] = None
    largura_cm: Optional[float] = None
    lateral_image: Optional[FishImageItem] = None
    superior_image: Optional[FishImageItem] = None


class FishAnalysisListResponse(BaseModel):
    items: List[FishAnalysisItem]
    total: int


class FishAnalysisDeleteResponse(BaseModel):
    id: str
    status: str
    message: str


# ── Processamento ──────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    lateral_id: str
    superior_id: str
    fator_lateral: Optional[float] = None   # px/cm manual (opcional)
    fator_superior: Optional[float] = None  # px/cm manual (opcional)
    peso_g: Optional[float] = None          # informe para calcular Kvol


class ProcessResponse(BaseModel):
    analysis_id: str
    status: str
    message: str
    comprimento_cm: Optional[float] = None
    altura_cm: Optional[float] = None
    largura_cm: Optional[float] = None
    kvol: Optional[float] = None
    lateral_metrics: Optional[Dict[str, Any]] = None
    superior_metrics: Optional[Dict[str, Any]] = None
    lateral_viz_b64: Optional[str] = None   # JPEG base64 com máscara + bbox
    superior_viz_b64: Optional[str] = None  # JPEG base64 com máscara + bbox
    warnings: List[str] = []
