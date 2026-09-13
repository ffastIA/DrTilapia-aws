// CAMINHO: frontend/hooks/useUpdateProfileMutation.ts
import { useState } from 'react';
import api from '@/lib/api';
import { ProfileUpsertPayload, UserProfile } from '@/types/profile';

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
  return 'Erro ao salvar o perfil. Tente novamente.';
}

export const useUpdateProfileMutation = () => {
  const [isPending, setIsPending] = useState(false);
  const [isError, setIsError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const mutate = async (
    payload: ProfileUpsertPayload,
    options?: {
      onSuccess?: (data: UserProfile) => void;
      onError?: (error: Error) => void;
      onSettled?: () => void;
    }
  ) => {
    setIsPending(true);
    setIsError(false);
    setIsSuccess(false);
    setError(null);

    try {
      const response = await api.put<UserProfile>('/profile', payload);
      setIsSuccess(true);
      options?.onSuccess?.(response.data);
    } catch (err: any) {
      const normalizedError = new Error(normalizeErrorMessage(err.response?.data?.detail ?? err.response?.data ?? err));
      setError(normalizedError);
      setIsError(true);
      options?.onError?.(normalizedError);
    } finally {
      setIsPending(false);
      options?.onSettled?.();
    }
  };

  return { mutate, isPending, isError, isSuccess, error };
};

export default useUpdateProfileMutation;
