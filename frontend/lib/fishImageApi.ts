// CAMINHO: frontend/lib/fishImageApi.ts

import api from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import type {
  FishImageListResponse,
  FishImageUploadResponse,
  FishImageDeleteResponse,
  FishAnalysisListResponse,
  ProcessRequest,
  ProcessResponse,
} from '@/types/fishImage';

// Mesmo proxy configurado em api.ts e next.config.js
const API_BASE_URL = '/api-proxy';

// ── Imagens ───────────────────────────────────────────────────────────────────

/**
 * Upload via fetch nativo — bypass do axios para FormData.
 *
 * Razão: o axios 1.x mergeia o header padrão Content-Type: application/json
 * da instância e não garante que o browser possa setar o boundary correto
 * para multipart/form-data. Sem o boundary o FastAPI não consegue parsear
 * o corpo e a requisição trava indefinidamente.
 *
 * Com fetch nativo: NÃO definimos Content-Type — o browser detecta FormData
 * e seta automaticamente "multipart/form-data; boundary=----..." correto.
 */
export async function uploadFishImage(
  file: File,
  tag: 'lateral' | 'superior',
  fatorConversao?: number | null,
): Promise<FishImageUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('tag', tag);
  if (fatorConversao != null) {
    form.append('fator_conversao', String(fatorConversao));
  }

  const token = useAuthStore.getState().token;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000); // 30s timeout

  try {
    const res = await fetch(`${API_BASE_URL}/fish/images/upload`, {
      method: 'POST',
      // SEM Content-Type: o browser seta multipart/form-data; boundary=... automaticamente
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
      signal: controller.signal,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      const msg = (errData as { detail?: string }).detail || `HTTP ${res.status}`;
      throw Object.assign(new Error(msg), { response: { data: errData } });
    }

    return res.json() as Promise<FishImageUploadResponse>;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw Object.assign(new Error('Tempo limite de upload excedido (30s)'), {
        response: { data: { detail: 'Tempo limite de upload excedido (30s)' } },
      });
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function listFishImages(params?: {
  tag?: string;
  date_from?: string;
  date_to?: string;
}): Promise<FishImageListResponse> {
  const response = await api.get('/fish/images', { params });
  return response.data;
}

export async function deleteFishImage(imageId: string): Promise<FishImageDeleteResponse> {
  const response = await api.delete(`/fish/images/${imageId}`);
  return response.data;
}

// ── Análises ──────────────────────────────────────────────────────────────────

export async function processFishAnalysis(
  data: ProcessRequest,
): Promise<ProcessResponse> {
  const response = await api.post('/fish/analyses/process', data);
  return response.data;
}

export async function listFishAnalyses(params?: {
  date_from?: string;
  date_to?: string;
  kvol_min?: number;
  kvol_max?: number;
}): Promise<FishAnalysisListResponse> {
  const response = await api.get('/fish/analyses', { params });
  return response.data;
}

export async function deleteFishAnalysis(analysisId: string): Promise<{ id: string; status: string; message: string }> {
  const response = await api.delete(`/fish/analyses/${analysisId}`);
  return response.data;
}
