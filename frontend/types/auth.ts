// types/auth.ts
export interface User {
  id: string;
  email: string;
  name?: string;
  role: 'admin' | 'user';
  created_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  // O token não é devolvido ao browser (cookie HttpOnly definido pelo servidor).
  token_type: string;
  profile_complete?: boolean;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => Promise<void>;
  restoreAuth: () => void;
}