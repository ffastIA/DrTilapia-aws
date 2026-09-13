// CAMINHO: frontend/hooks/useSignupMutation.ts
import { useState } from 'react';
import api from '@/lib/api';

interface SignupRequest {
  email: string;
  password: string;
}

interface MessageResponse {
  message: string;
}

function normalizeErrorMessage(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'object' && item && 'msg' in item && typeof item.msg === 'string') {
          return item.msg;
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }
  if (typeof value === 'object' && value !== null) {
    if ('msg' in value && typeof value.msg === 'string') {
      return value.msg;
    }
    if ('detail' in value) {
      return normalizeErrorMessage((value as any).detail);
    }
  }
  return 'Erro ao criar a conta. Tente novamente.';
}

export const useSignupMutation = () => {
  const [isPending, setIsPending] = useState(false);
  const [isError, setIsError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<MessageResponse | null>(null);

  const mutate = async (
    credentials: SignupRequest,
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
      const response = await api.post<MessageResponse>('/auth/signup', credentials);
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
