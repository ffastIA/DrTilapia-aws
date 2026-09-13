// CAMINHO: frontend/hooks/useVideoAdmin.ts

import { useCallback, useState } from 'react';
import { deleteVideo as deleteVideoApi, uploadVideo as uploadVideoApi } from '@/lib/videoApi';
import type { VideoError } from '@/types/video';

/**
 * Hook de escrita para administradores: upload e exclusão de vídeos.
 *
 * @param onSuccess  Callback chamado após upload ou delete bem-sucedido
 *                   (normalmente refresh() do useVideos).
 *
 * Ambas as operações retornam `boolean` para que o chamador saiba
 * se deve fechar modais ou manter o formulário aberto em caso de erro.
 */
export default function useVideoAdmin(onSuccess?: () => void) {
  const [isUploading, setUploading] = useState<boolean>(false);
  const [isDeleting,  setDeleting]  = useState<boolean>(false);
  const [feedback,    setFeedback]  = useState<string>('');
  const [error,       setError]     = useState<VideoError | null>(null);

  const resetFeedback = useCallback(() => {
    setFeedback('');
    setError(null);
  }, []);

  /** Faz upload. Retorna true em sucesso, false em falha. */
  const uploadVideo = useCallback(async (
    file:        File,
    title:       string,
    description: string,
    category:    string,
  ): Promise<boolean> => {
    setUploading(true);
    setFeedback('');
    setError(null);
    try {
      await uploadVideoApi(file, title, description, category);
      setFeedback('Vídeo enviado com sucesso!');
      onSuccess?.();
      return true;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Erro ao enviar vídeo';
      setError({ message: msg });
      return false;
    } finally {
      setUploading(false);
    }
  }, [onSuccess]);

  /** Remove um vídeo. Retorna true em sucesso, false em falha. */
  const deleteVideo = useCallback(async (videoId: string): Promise<boolean> => {
    setDeleting(true);
    setFeedback('');
    setError(null);
    try {
      await deleteVideoApi(videoId);
      setFeedback('Vídeo removido com sucesso.');
      onSuccess?.();
      return true;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Erro ao remover vídeo';
      setError({ message: msg });
      return false;
    } finally {
      setDeleting(false);
    }
  }, [onSuccess]);

  return {
    isUploading,
    isDeleting,
    feedback,
    error,
    uploadVideo,
    deleteVideo,
    resetFeedback,
  };
}
