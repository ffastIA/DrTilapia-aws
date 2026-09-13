// CAMINHO: frontend/hooks/useVideos.ts

import { useCallback, useEffect, useState } from 'react';
import { listVideos } from '@/lib/videoApi';
import type { VideoError, VideoItem } from '@/types/video';

/**
 * Hook de leitura: busca a lista de vídeos ao montar e expõe refresh().
 * Disponível para qualquer usuário autenticado.
 */
export default function useVideos() {
  const [videos, setVideos]   = useState<VideoItem[]>([]);
  const [total, setTotal]     = useState<number>(0);
  const [isLoading, setLoading] = useState<boolean>(false);
  const [error, setError]     = useState<VideoError | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listVideos();
      setVideos(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Erro ao carregar vídeos';
      setError({ message: msg });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { videos, total, isLoading, error, refresh };
}
