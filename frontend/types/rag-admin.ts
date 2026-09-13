// CAMINHO: frontend/types/rag-admin.ts

// Tipos base e utilitários
export type RagAdminError = {
  message: string;
  code?: string;
  details?: any;
};

export type OperationStatus = 'idle' | 'loading' | 'success' | 'error';

export type CriticalActionType = 'delete_item' | 'clear_all';

// Tipos brutos do backend (flexíveis para adaptação)
export interface RawRagItem {
  id: string;
  title?: string;
  content?: string;
  metadata?: Record<string, any>;
  createdAt?: string;
  updatedAt?: string;
  // Campos adicionais flexíveis para variações do backend
  [key: string]: any;
}

export interface RawRagListResponse {
  items: RawRagItem[];
  total?: number;
  page?: number;
  limit?: number;
  // Outros campos possíveis
  [key: string]: any;
}

export interface RawRagUploadResponse {
  uploaded: RawRagItem[];
  failed?: { file: string; error: string }[];
  totalUploaded?: number;
  totalFailed?: number;
  // Para uploads múltiplos e status por item
  [key: string]: any;
}

export interface RawRagDeleteResponse {
  deleted: string[]; // IDs deletados
  failed?: { id: string; error: string }[];
  [key: string]: any;
}

export interface RawRagClearResponse {
  cleared: boolean;
  count?: number;
  [key: string]: any;
}

// Tipos normalizados para UI (estáveis e padronizados)
export interface RagItem {
  id: string;
  title: string;
  content: string;
  metadata: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}

export interface RagListResponse {
  items: RagItem[];
  total: number;
  page: number;
  limit: number;
}

export interface RagUploadResponse {
  uploaded: RagItem[];
  failed: { file: string; error: string }[];
  totalUploaded: number;
  totalFailed: number;
}

export interface RagDeleteResponse {
  deleted: string[];
  failed: { id: string; error: string }[];
}

export interface RagClearResponse {
  cleared: boolean;
  count: number;
}

// Utilitários para adaptação de respostas cruas do backend para objetos de UI
export type NormalizeRagItem = (raw: RawRagItem) => RagItem;
export type NormalizeRagListResponse = (raw: RawRagListResponse) => RagListResponse;
export type NormalizeRagUploadResponse = (raw: RawRagUploadResponse) => RagUploadResponse;
export type NormalizeRagDeleteResponse = (raw: RawRagDeleteResponse) => RagDeleteResponse;
export type NormalizeRagClearResponse = (raw: RawRagClearResponse) => RagClearResponse;

// Payloads de operações
export interface RagUploadPayload {
  files: File[];
  metadata?: Record<string, any>;
}

export interface RagDeletePayload {
  ids: string[];
}

export interface RagClearPayload {
  confirm: boolean;
}

// Estados de operação no frontend
export interface RagAdminState {
  list: {
    items: RagItem[];
    total: number;
    status: OperationStatus;
    error?: RagAdminError;
  };
  upload: {
    status: OperationStatus;
    response?: RagUploadResponse;
    error?: RagAdminError;
  };
  delete: {
    status: OperationStatus;
    response?: RagDeleteResponse;
    error?: RagAdminError;
  };
  clear: {
    status: OperationStatus;
    response?: RagClearResponse;
    error?: RagAdminError;
  };
}