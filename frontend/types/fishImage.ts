// CAMINHO: frontend/types/fishImage.ts

export interface FishImageItem {
  id: string;
  analysis_id?: string | null;
  user_id: string;
  tag: 'lateral' | 'superior';
  filename: string;
  storage_path: string;
  uploaded_at: string;
  url?: string | null;
  fator_conversao?: number | null;
  bbox_width_px?: number | null;
  bbox_height_px?: number | null;
  bbox_width_cm?: number | null;
  bbox_height_cm?: number | null;
  mask_area_px?: number | null;
  mask_area_cm2?: number | null;
  peso_g?: number | null;
  processing_status: 'pending' | 'processing' | 'done' | 'error';
  processing_error?: string | null;
  processed_at?: string | null;
}

export interface FishImageListResponse {
  items: FishImageItem[];
  total: number;
}

export interface FishImageUploadResponse {
  id: string;
  tag: string;
  filename: string;
  storage_path: string;
  status: string;
  message: string;
}

export interface FishImageDeleteResponse {
  id: string;
  status: string;
  message: string;
  storage_deleted: boolean;
}

export interface FishAnalysisItem {
  id: string;
  user_id: string;
  created_at: string;
  peso_g?: number | null;
  kvol?: number | null;
  comprimento_cm?: number | null;
  altura_cm?: number | null;
  largura_cm?: number | null;
  lateral_image?: FishImageItem | null;
  superior_image?: FishImageItem | null;
}

export interface FishAnalysisListResponse {
  items: FishAnalysisItem[];
  total: number;
}

export interface ProcessRequest {
  lateral_id: string;
  superior_id: string;
  fator_lateral?: number | null;
  fator_superior?: number | null;
  peso_g?: number | null;
}

export interface ProcessResponse {
  analysis_id: string;
  status: string;
  message: string;
  comprimento_cm?: number | null;
  altura_cm?: number | null;
  largura_cm?: number | null;
  kvol?: number | null;
  lateral_metrics?: Record<string, unknown> | null;
  superior_metrics?: Record<string, unknown> | null;
  lateral_viz_b64?: string | null;   // JPEG base64 com máscara + bbox
  superior_viz_b64?: string | null;  // JPEG base64 com máscara + bbox
  warnings: string[];
}

export interface FishError {
  message: string;
  status?: number;
}
