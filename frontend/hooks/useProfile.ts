// CAMINHO: frontend/hooks/useProfile.ts
import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { UserProfile } from '@/types/profile';

export const useProfile = () => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const setUserName = useAuthStore((state) => state.setUserName);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      const response = await api.get<UserProfile>('/profile');
      setProfile(response.data);
      if (response.data.full_name) {
        setUserName(response.data.full_name);
      }
    } catch {
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  }, [setUserName]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { profile, isLoading, isError, refetch };
};

export default useProfile;
