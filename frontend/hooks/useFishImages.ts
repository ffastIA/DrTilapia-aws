// CAMINHO: frontend/hooks/useFishImages.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import { listFishImages, deleteFishImage } from '@/lib/fishImageApi';
import type { FishImageItem, FishError } from '@/types/fishImage';

interface UseFishImagesOptions {
  tag?: string;
  autoFetch?: boolean;
}

export default function useFishImages({ tag, autoFetch = true }: UseFishImagesOptions = {}) {
  const [images, setImages] = useState<FishImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<FishError | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listFishImages({ tag });
      setImages(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro ao carregar imagens' });
    } finally {
      setIsLoading(false);
    }
  }, [tag]);

  useEffect(() => {
    if (autoFetch) refresh();
  }, [autoFetch, refresh]);

  const deleteImage = useCallback(async (imageId: string): Promise<boolean> => {
    setIsDeleting(true);
    try {
      await deleteFishImage(imageId);
      setImages((prev) => prev.filter((img) => img.id !== imageId));
      setTotal((prev) => prev - 1);
      return true;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro ao excluir imagem' });
      return false;
    } finally {
      setIsDeleting(false);
    }
  }, []);

  return { images, total, isLoading, error, isDeleting, refresh, deleteImage };
}
