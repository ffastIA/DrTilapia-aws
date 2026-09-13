// CAMINHO: frontend/lib/videoApi.ts

import api from '@/lib/api';
import type { VideoDeleteResponse, VideoListResponse, VideoUploadResponse } from '@/types/video';

const VIDEO_ENDPOINTS = {
  LIST:        '/videos',
  UPLOAD:      '/videos/upload',
  DELETE_BASE: '/videos',
} as const;

/** Lista todos os vídeos disponíveis com signed URLs de 24 h. */
export async function listVideos(): Promise<VideoListResponse> {
  const response = await api.get(VIDEO_ENDPOINTS.LIST);
  const body = response?.data as VideoListResponse | undefined;
  return {
    items: body?.items ?? [],
    total: body?.total ?? 0,
  };
}

/**
 * Faz upload de um vídeo (multipart/form-data).
 * Requer token de admin no header Authorization.
 */
export async function uploadVideo(
  file: File,
  title: string,
  description: string,
  category: string,
): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', title);
  formData.append('description', description);
  formData.append('category', category);

  const response = await api.post(VIDEO_ENDPOINTS.UPLOAD, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data as VideoUploadResponse;
}

/**
 * Remove um vídeo do Storage e da tabela.
 * Requer token de admin no header Authorization.
 */
export async function deleteVideo(videoId: string): Promise<VideoDeleteResponse> {
  const response = await api.delete(
    `${VIDEO_ENDPOINTS.DELETE_BASE}/${encodeURIComponent(videoId)}`,
  );
  return response.data as VideoDeleteResponse;
}
