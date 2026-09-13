'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import LoadingSpinner from './LoadingSpinner';

interface AuthProviderProps {
  children: React.ReactNode;
}

const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const { isAuthenticated, isLoading, restoreAuth } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  // Restaurar auth IMEDIATAMENTE (é síncrono, apenas lê cookies)
  useEffect(() => {
    restoreAuth();
    setMounted(true);
  }, []);

  // Redirecionar APENAS após auth estar restaurado
  useEffect(() => {
    if (!mounted || isLoading) return;

    const protectedRoutes = ['/main'];
    const isProtectedRoute = protectedRoutes.some(route => pathname.startsWith(route));

    if (!isAuthenticated && isProtectedRoute) {
      router.push('/auth/login');
    } else if (isAuthenticated && pathname === '/auth/login') {
      router.push('/main/hub');
    }
  }, [isAuthenticated, isLoading, pathname, router, mounted]);

  // Se ainda está carregando, mostrar spinner
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <LoadingSpinner size="w-12 h-12" color="text-primary" />
      </div>
    );
  }

  return <>{children}</>;
};

export default AuthProvider;