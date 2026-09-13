// CAMINHO: frontend/hooks/useForgotPasswordMutation.ts
import { useState } from 'react';
import api from '@/lib/api';

interface ForgotPasswordRequest {
  email: string;
}

interface MessageResponse {
  message: string;
}

function normalizeErrorMessage(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'object' && value !== null && 'detail' in value) {
    return normalizeErrorMessage((value as any).detail);
  }
  return 'Erro ao solicitar a redefinição de senha. Tente novamente.';
}

export const useForgotPasswordMutation = () => {
  const [isPending, setIsPending] = useState(false);
  const [isError, setIsError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<MessageResponse | null>(null);

  const mutate = async (
    credentials: ForgotPasswordRequest,
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
      const response = await api.post<MessageResponse>('/auth/forgot-password', credentials);
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
