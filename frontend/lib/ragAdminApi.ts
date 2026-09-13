// CAMINHO: frontend/lib/ragAdminApi.ts

import api from '@/lib/api';
import type { RagAdminError, RagClearResponse, RagDeletePayload, RagDeleteResponse, RagItem, RagListResponse, RagUploadResponse } from '@/types/rag-admin';

export const RAG_ADMIN_ENDPOINTS = {
  LIST: '/admin/vector-base/files',
  UPLOAD: '/admin/upload',
  DELETE_BASE: '/admin/vector-base/files',
  CLEAR: '/admin/vector-base/cleanup',
} as const;

export type RagOperationStatusResponse = {
  status: 'completed' | 'in_progress' | 'failed';
  progress?: number;
  message?: string;
  jobId?: string;
};

function extractBody(response: any): any {
  return response?.data ?? response?.body ?? response ?? null;
}

function getFirstDefined<T>(...values: Array<T | null | undefined | ''>): T | undefined {
  for (const value of values) {
    if (value != null && value !== '') {
      return value as T;
    }
  }
  return undefined;
}

function toDateOrNull(value: unknown): Date | null {
  if (!value) return null;
  const date = new Date(value as string | number | Date);
  return isNaN(date.getTime()) ? null : date;
}

function normalizeItem(raw: any): RagItem | null {
  const id = getFirstDefined(
    raw?.original_file_id,
    raw?.id,
    raw?.file_id,
    raw?.document_id
  ) as string | undefined;

  if (!id) {
    return null;
  }

  const title =
    (getFirstDefined(
      raw?.original_file_name,
      raw?.filename,
      raw?.file_name,
      raw?.title,
      raw?.name
    ) as string) || 'Sem título';

  const content =
    (getFirstDefined(raw?.content, raw?.summary, raw?.text) as string) || '';

  const createdSource = getFirstDefined(
    raw?.last_ingested_at,
    raw?.created_at,
    raw?.createdAt,
    raw?.metadata?.created_at
  );

  const updatedSource = getFirstDefined(
    raw?.updated_at,
    raw?.updatedAt,
    raw?.last_ingested_at,
    raw?.metadata?.updated_at
  );

  const createdAt = toDateOrNull(createdSource) || new Date('1970-01-01T00:00:00.000Z');
  const updatedAt = toDateOrNull(updatedSource) || new Date('1970-01-01T00:00:00.000Z');

  const metadata: RagItem['metadata'] = {
    source: raw?.original_file_name || raw?.metadata?.source || title,
    storage_bucket: raw?.storage_bucket,
    storage_path: raw?.storage_path,
    total_chunks: raw?.total_chunks,
    active_chunks: raw?.active_chunks,
    deleted_chunks: raw?.deleted_chunks,
    status: raw?.status,
    deleted_at: raw?.deleted_at,
    hasValidCreatedAt: !!toDateOrNull(createdSource),
    hasValidUpdatedAt: !!toDateOrNull(updatedSource),
  };

  return {
    id,
    title,
    content,
    metadata,
    createdAt,
    updatedAt,
  };
}

function normalizeUploadItemFromResponse(raw: any, file: File): RagItem {
  const item = normalizeItem({ ...raw, original_file_name: file.name });
  if (!item) {
    return {
      id: raw?.id || raw?.original_file_id || '',
      title: file.name,
      content: '',
      metadata: {
        source: file.name,
      },
      createdAt: new Date(),
      updatedAt: new Date(),
    };
  }
  return {
    ...item,
    title: item.title || file.name,
    metadata: {
      ...item.metadata,
      source: file.name,
    },
  };
}

function normalizeError(error: any): RagAdminError {
  return {
    message: error?.message || error?.error || 'Erro desconhecido',
    code: error?.code,
    details: error?.details || error,
  };
}

export async function listRagDocuments(): Promise<RagListResponse> {
  const response = await api.get(RAG_ADMIN_ENDPOINTS.LIST);
  const body = extractBody(response);
  const itemsRaw = body?.items || body || [];
  const itemsRawArray = Array.isArray(itemsRaw) ? itemsRaw : [itemsRaw];
  const items = itemsRawArray
    .map(normalizeItem)
    .filter((item): item is RagItem => item !== null && !!item.id) as RagItem[];
  return {
    items,
    total: items.length,
    page: 1,
    limit: items.length,
  };
}

export async function uploadRagDocuments(
  files: File[],
  extraData?: Record<string, any>
): Promise<RagUploadResponse> {
  if (!files?.length) {
    throw new Error('Nenhum arquivo selecionado para upload.');
  }

  const uploaded: RagItem[] = [];
  const failed: { file: string; error: string }[] = [];

  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (extraData) {
        Object.entries(extraData).forEach(([key, value]) => {
          formData.append(key, String(value));
        });
      }
      const response = await api.post(RAG_ADMIN_ENDPOINTS.UPLOAD, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const body = extractBody(response);
      const item = normalizeUploadItemFromResponse(body, file);
      uploaded.push(item);
    } catch (error) {
      failed.push({
        file: file.name,
        error: normalizeError(error).message,
      });
    }
  }

  return {
    uploaded,
    failed,
    totalUploaded: uploaded.length,
    totalFailed: failed.length,
  };
}

export async function deleteRagDocument(
  payload: RagDeletePayload | { id?: string; ids?: string[]; delete_chunks?: boolean; [key: string]: unknown }
): Promise<RagDeleteResponse> {
  const loosePayload = payload as { id?: string; ids?: string[] };

  let ids: string[] = [];
  if (Array.isArray(loosePayload.ids)) {
    ids.push(...loosePayload.ids);
  }
  if (loosePayload.id) {
    ids.push(loosePayload.id);
  }
  ids = ids.filter((id) => !!id && id.trim().length > 0);

  if (!ids.length) {
    throw new Error('Nenhum ID válido foi informado para exclusão.');
  }

  const deleted: string[] = [];
  const failed: { id: string; error: string }[] = [];

  for (const id of ids) {
    try {
      await api.post(`${RAG_ADMIN_ENDPOINTS.DELETE_BASE}/${encodeURIComponent(id)}/delete`, payload);
      deleted.push(id);
    } catch (error) {
      failed.push({
        id,
        error: normalizeError(error).message,
      });
    }
  }

  return {
    deleted,
    failed,
  };
}

export async function clearRagDatabase(confirm?: boolean): Promise<RagClearResponse> {
  const body = {
    confirmation_phrase: confirm ? 'CONFIRMADO' : undefined,
    dry_run: !confirm,
  };

  const response = await api.post(RAG_ADMIN_ENDPOINTS.CLEAR, body);
  const resBody = extractBody(response);
  const cleared = !!getFirstDefined(resBody?.success, resBody?.cleared, true);
  const count = getFirstDefined<number>(
    resBody?.total_documents_deleted,
    resBody?.count,
    resBody?.affected_count,
    resBody?.deleted_count,
    resBody?.total,
    0
  );

  return {
    cleared,
    count: count ?? 0,
  };
}

export async function getRagOperationStatus(_jobId: string): Promise<RagOperationStatusResponse> {
  throw new Error('Status de operação não está disponível no backend atual.');
}

export const ragAdminApi = {
  listRagDocuments,
  uploadRagDocuments,
  deleteRagDocument,
  clearRagDatabase,
  getRagOperationStatus,
} as const;

export default ragAdminApi;
