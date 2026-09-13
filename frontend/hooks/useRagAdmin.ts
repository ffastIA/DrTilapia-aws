// CAMINHO: frontend/hooks/useRagAdmin.ts
import { useCallback, useEffect, useState } from 'react';
import { clearRagDatabase, deleteRagDocument, listRagDocuments, uploadRagDocuments } from '@/lib/ragAdminApi';
import type { RagAdminError, RagClearResponse, RagDeleteResponse, RagItem, RagUploadResponse } from '@/types/rag-admin';

function normalizeUiError(error: unknown): RagAdminError {
  if (error && typeof error === 'object' && 'message' in error) {
    return error as RagAdminError;
  }
  return { message: 'Erro desconhecido ocorreu.' };
}

function hasValidItemId(item: RagItem | null | undefined): item is RagItem {
  return item !== null && item !== undefined && item.id !== '' && item.id !== null && item.id !== undefined;
}

export default function useRagAdmin() {
  const [items, setItems] = useState<RagItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit, setLimit] = useState<number>(0);
  const [selectedItem, setSelectedItem] = useState<RagItem | null>(null);
  const [criticalAction, setCriticalAction] = useState<'delete_item' | 'clear_all' | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState<boolean>(false);
  const [isLoadingList, setIsLoadingList] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [listError, setListError] = useState<RagAdminError | null>(null);
  const [operationMessage, setOperationMessage] = useState<string>('');
  const [operationError, setOperationError] = useState<RagAdminError | null>(null);
  const [lastUploadResponse, setLastUploadResponse] = useState<RagUploadResponse | null>(null);
  const [lastDeleteResponse, setLastDeleteResponse] = useState<RagDeleteResponse | null>(null);
  const [lastClearResponse, setLastClearResponse] = useState<RagClearResponse | null>(null);

  const refreshList = useCallback(async () => {
    setListError(null);
    setIsLoadingList(true);
    try {
      const response = await listRagDocuments();
      setItems(response.items);
      setTotal(response.total);
      setPage(response.page);
      setLimit(response.limit);
    } catch (error) {
      setListError(normalizeUiError(error));
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const openDeleteModal = useCallback((item: RagItem) => {
    if (!hasValidItemId(item)) {
      setOperationError({ message: 'Não foi possível excluir: documento sem ID válido.' });
      return;
    }
    setSelectedItem(item);
    setCriticalAction('delete_item');
    setIsDeleteModalOpen(true);
    setOperationError(null);
  }, []);

  const closeDeleteModal = useCallback(() => {
    setIsDeleteModalOpen(false);
    setSelectedItem(null);
    setCriticalAction(null);
  }, []);

  const deleteSelectedItem = useCallback(async () => {
    if (!hasValidItemId(selectedItem)) {
      setOperationError({ message: 'Não foi possível excluir: documento sem ID válido.' });
      return;
    }
    setIsDeleting(true);
    setOperationMessage('');
    setOperationError(null);
    try {
      const response = await deleteRagDocument({
        ids: [selectedItem.id],
        delete_chunks: true,
        confirmation_phrase: 'CONFIRMADO',
      });
      setLastDeleteResponse(response);
      if (response.deleted.length > 0) {
        setOperationMessage('Arquivo excluído com sucesso.');
        await refreshList();
        closeDeleteModal();
      } else {
        const errorMsg = response.failed.length > 0 ? response.failed[0].error : 'Falha ao excluir o arquivo.';
        setOperationError({ message: errorMsg });
      }
    } catch (error) {
      setOperationError(normalizeUiError(error));
    } finally {
      setIsDeleting(false);
    }
  }, [selectedItem, refreshList, closeDeleteModal]);

  const uploadFiles = useCallback(async (files: File[], extraData?: Record<string, unknown>) => {
    setIsUploading(true);
    setOperationMessage('');
    setOperationError(null);
    try {
      const response = await uploadRagDocuments(files, extraData);
      setLastUploadResponse(response);
      if (response.totalUploaded > 0) {
        const msg = response.totalUploaded === 1 ? 'Arquivo enviado com sucesso.' : `${response.totalUploaded} arquivos enviados com sucesso.`;
        setOperationMessage(msg);
        await refreshList();
      } else if (response.totalUploaded === 0 && response.totalFailed > 0) {
        const errorMsg = response.failed.length > 0 ? response.failed[0].error : 'Falha ao enviar os arquivos.';
        setOperationError({ message: errorMsg });
      }
    } catch (error) {
      setOperationError(normalizeUiError(error));
    } finally {
      setIsUploading(false);
    }
  }, [refreshList]);

  const clearDatabase = useCallback(async (confirm?: boolean) => {
    setIsClearing(true);
    setOperationMessage('');
    setOperationError(null);
    try {
      const response = await clearRagDatabase(confirm);
      setLastClearResponse(response);
      if (confirm === true) {
        setOperationMessage('Limpeza executada com sucesso.');
        await refreshList();
      } else {
        setOperationMessage('Simulação de limpeza executada.');
      }
    } catch (error) {
      setOperationError(normalizeUiError(error));
    } finally {
      setIsClearing(false);
    }
  }, [refreshList]);

  const resetFeedback = useCallback(() => {
    setOperationMessage('');
    setOperationError(null);
  }, []);

  return {
    items,
    total,
    page,
    limit,
    selectedItem,
    criticalAction,
    isDeleteModalOpen,
    isLoadingList,
    isUploading,
    isDeleting,
    isClearing,
    listError,
    operationMessage,
    operationError,
    lastUploadResponse,
    lastDeleteResponse,
    lastClearResponse,
    refreshList,
    uploadFiles,
    openDeleteModal,
    closeDeleteModal,
    deleteSelectedItem,
    clearDatabase,
    resetFeedback,
  };
}