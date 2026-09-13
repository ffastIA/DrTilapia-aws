// CAMINHO: frontend/hooks/useResetPasswordMutation.ts
import { useState } from 'react';
import api from '@/lib/api';

interface ResetPasswordRequest {
  access_token: string;
  refresh_token: string;
  new_password: string;
}

interface MessageResponse {
  message: string;
}

const KNOWN_ERROR_MESSAGES: Record<string, string> = {
  invalid_reset_token: 'Link inválido ou expirado. Solicite um novo.',
  reset_failed: 'Não foi possível redefinir a senha. Tente novamente.',
};

function normalizeErrorMessage(value: unknown): string {
  if (typeof value === 'string') {
    return KNOWN_ERROR_MESSAGES[value] || value;
  }
  if (typeof value === 'object' && value !== null && 'detail' in value) {
    return normalizeErrorMessage((value as any).detail);
  }
  return 'Não foi possível redefinir a senha. Tente novamente.';
}

export const useResetPasswordMutation = () => {
  const [isPending, setIsPending] = useState(false);
  const [isError, setIsError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<MessageResponse | null>(null);

  const mutate = async (
    credentials: ResetPasswordRequest,
    options?: {
      onSuccess?: (data: MessageResponse) => void;
      onError?: (error: Error) => void;
      onSettled?: () => void;
    }
  ) => {
    setIsPending(true);
    setIsError(false);
    setIsSuccess(false);
    setError(null);
    setData(null);

    try {
      const response = await api.post<MessageResponse>('/auth/reset-password', credentials);
      setData(response.data);
      setIsSuccess(true);
      options?.onSuccess?.(response.data);
    } catch (err: any) {
      const normalizedError = new Error(normalizeErrorMessage(err.response?.data ?? err));
      setError(normalizedError);
      setIsError(true);
      options?.onError?.(normalizedError);
    } finally {
      setIsPending(false);
      options?.onSettled?.();
    }
  };

  return { mutate, isPending, isError, isSuccess, error, data };
};
