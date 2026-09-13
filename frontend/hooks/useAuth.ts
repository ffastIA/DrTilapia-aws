// CAMINHO: frontend/hooks/useAuth.ts

import { useAuthStore } from '@/store/authStore';

// Hook personalizado para autenticação
const useAuth = () => {
  // Obtém os valores do store
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoading = useAuthStore((state) => state.isLoading);
  const setAuth = useAuthStore((state) => state.setAuth);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const restoreAuth = useAuthStore((state) => state.restoreAuth);

  // Função para atualizar o usuário, preservando outros campos
  const updateUser = (newUser: typeof user) => {
    useAuthStore.setState((state) => ({ ...state, user: newUser }));
  };

  // Retorna os valores e funções necessários
  return {
    user,
    token,
    isAuthenticated,
    isLoading,
    restoreAuth,
    login: setAuth, // Alias para setAuth
    logout: clearAuth, // Alias para clearAuth
    updateUser,
  };
};

export { useAuth };
export default useAuth;
