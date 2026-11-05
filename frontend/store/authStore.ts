// CAMINHO: frontend/store/authStore.ts

import { create } from 'zustand';
import Cookies from 'js-cookie';

interface User {
  id: string;
  email: string;
  role: 'admin' | 'user';
  name?: string;
}

interface AuthStore {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (token: string, user: User) => void;
  setUserName: (name: string) => void;
  clearAuth: () => Promise<void>;
  restoreAuth: () => void;
}

// Cache positivo do gate de cadastro (spec `profile-onboarding-gate`): só grava
// quando o cadastro está completo, nunca o estado "incompleto". `Secure` segue o
// protocolo da página (cookie Secure é descartado em http://), como em setAuth.
export const setProfileCompleteCookie = () => {
  Cookies.set('profileComplete', '1', {
    path: '/',
    sameSite: 'Lax',
    secure: window.location.protocol === 'https:',
  });
};

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
  setAuth: (_token, user) => {
    // Cookie "Secure" é descartado pelo browser em http:// (ex.: CloudFront sem TLS),
    // o que impede o middleware de ver o token e devolve o usuário ao login.
    // O token de sessão NÃO é gravado aqui: o servidor o define em cookie
    // HttpOnly (/api/auth/login). Só o perfil não sensível fica legível ao JS.
    const secure = window.location.protocol === 'https:';
    Cookies.set('user', JSON.stringify(user), { path: '/', sameSite: 'Lax', secure });
    set({ token: null, user, isAuthenticated: true, isLoading: false });
  },
  setUserName: (name) => {
    const currentUser = get().user;
    if (!currentUser || currentUser.name === name) return;
    const updatedUser = { ...currentUser, name };
    Cookies.set('user', JSON.stringify(updatedUser), { path: '/', sameSite: 'Lax', secure: window.location.protocol === 'https:' });
    set({ user: updatedUser });
  },
  clearAuth: async () => {
    // Revoga a sessão no servidor e remove os cookies HttpOnly (best effort).
    // Aguardado para que a navegação seguinte já não encontre o cookie de sessão.
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {});
    Cookies.remove('accessToken', { path: '/' });
    Cookies.remove('user', { path: '/' });
    Cookies.remove('profileGateSeen', { path: '/' });
    Cookies.remove('profileComplete', { path: '/' });
    set({ token: null, user: null, isAuthenticated: false, isLoading: false });
  },
  restoreAuth: () => {
    // O cookie de sessão é HttpOnly (invisível ao JS): o cookie `user` indica a
    // sessão; o middleware/servidor é quem valida o token de fato.
    const userCookie = Cookies.get('user');
    if (userCookie) {
      try {
        const user = JSON.parse(userCookie);
        set({ token: null, user, isAuthenticated: true, isLoading: false });
      } catch {
        // JSON inválido, limpar cookies
        Cookies.remove('accessToken', { path: '/' });
        Cookies.remove('user', { path: '/' });
        set({ token: null, user: null, isAuthenticated: false, isLoading: false });
      }
    } else {
      // Cookies não existem
      set({ token: null, user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
