// CAMINHO: frontend/types/video.ts

export interface VideoItem {
  id: string;
  title: string;
  description?: string | null;
  category: string;
  filename: string;
  file_size?: number | null;  // bytes
  url: string;                // signed URL de 24h
  created_at: string;
  uploaded_by?: string | null;
}

export interface VideoListResponse {
  items: VideoItem[];
  total: number;
}

export interface VideoUploadResponse {
  id: string;
  title: string;
  category: string;
  filename: string;
  storage_path: string;
  file_size: number;
  status: string;
  message: string;
}

export interface VideoDeleteResponse {
  id: string;
  status: string;
  message: string;
  storage_deleted: boolean;
}

export interface VideoError {
  message: string;
}
