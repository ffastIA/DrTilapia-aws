// CAMINHO: frontend/middleware.ts
//
// Middleware do Next.js — executado no servidor antes de cada request.
// Protege rotas sem depender de JavaScript no cliente.
//
// Regras:
//  1. /main/*  sem cookie de token   → redireciona para /auth/login
//  2. /auth/login ou /auth/signup com cookie de token → redireciona para
//     /main/hub (já logado). As demais páginas de /auth/* (callback,
//     forgot-password) ficam de fora dessa regra de propósito: alguém pode
//     chegar ali por um link de email ainda com um cookie de sessão antigo
//     no navegador, e não deve ser expulso antes de completar o fluxo.
//  3. /main/* (exceto /main/profile) com perfil incompleto:
//       - primeira tentativa na sessão → redireciona silenciosamente para
//         /main/profile (não desloga)
//       - tentativa seguinte (usuário já tentou sair uma vez sem completar
//         o cadastro) → DESLOGA: redireciona para /auth/login expirando os
//         cookies de sessão (o cadastro é obrigatório — spec
//         `profile-onboarding-gate`, change fix-login-first-access-redirect)
//       - ATENÇÃO: o Next 14 remove os cabeçalhos RSC/Next-Router-Prefetch antes
//         de chamar o middleware, então aqui não dá para distinguir prefetch de
//         navegação real. Por isso as telas que um usuário com cadastro
//         incompleto enxerga (/main/profile e app/main/layout.tsx) NÃO podem ter
//         <Link> com prefetch para outras rotas de /main/* — senão o prefetch
//         consumiria o aviso e deslogaria o usuário sozinho.
//     "Perfil completo" = existe uma linha em public.user_profiles para o
//     usuário (as colunas obrigatórias são NOT NULL, então a existência da
//     linha já garante que os campos obrigatórios foram preenchidos — ver
//     openspec/changes/add-profile-onboarding-gate/design.md).
//     Este gate NÃO é um controle de segurança (o cookie profileComplete é
//     gravável pelo navegador) — é só um empurrão de completude de cadastro,
//     diferente do gate de admin abaixo, que sempre revalida contra a API.
//  4. /main/admin  sem role=admin    → redireciona para /main/hub
//     (o papel é verificado contra a API REST do Supabase usando o próprio
//     access token do usuário — nunca a partir do cookie `user`, que é
//     gravável pelo próprio navegador e não prova nada por si só. A policy
//     de RLS `users_select_own` garante que a consulta só retorna a linha
//     do usuário autenticado pelo token.)

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

async function isAdminToken(token: string): Promise<boolean> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    // Configuração ausente — nega por padrão em vez de abrir uma falha de segurança silenciosa.
    return false;
  }
  try {
    const response = await fetch(`${SUPABASE_URL}/rest/v1/users?select=role`, {
      headers: {
        Authorization: `Bearer ${token}`,
        apikey: SUPABASE_ANON_KEY,
      },
      cache: 'no-store',
    });
    if (!response.ok) {
      return false;
    }
    const rows = (await response.json()) as { role?: string }[];
    return Array.isArray(rows) && rows.length === 1 && rows[0]?.role === 'admin';
  } catch {
    // Rede indisponível/erro de parsing — falha fechada (nega acesso).
    return false;
  }
}

async function hasCompletedProfile(token: string): Promise<boolean> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    // Configuração ausente — assume incompleto (mais restritivo) em vez de liberar por engano.
    return false;
  }
  try {
    const response = await fetch(`${SUPABASE_URL}/rest/v1/user_profiles?select=user_id&limit=1`, {
      headers: {
        Authorization: `Bearer ${token}`,
        apikey: SUPABASE_ANON_KEY,
      },
      cache: 'no-store',
    });
    if (!response.ok) {
      // Distingue "consulta falhou" de "sem cadastro" nos logs (sem dados sensíveis).
      console.warn(`[middleware] hasCompletedProfile: Supabase respondeu HTTP ${response.status}`);
      return false;
    }
    const rows = (await response.json()) as { user_id?: string }[];
    return Array.isArray(rows) && rows.length === 1;
  } catch (error) {
    console.warn('[middleware] hasCompletedProfile: falha de rede/parsing', error instanceof Error ? error.message : error);
    return false;
  }
}

// Cookies de sessão/gate removidos no logout por abandono do cadastro (mesma
// lista de authStore.clearAuth).
const SESSION_COOKIES = ['accessToken', 'user', 'profileGateSeen', 'profileComplete'];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const token = request.cookies.get('accessToken')?.value;

  const isProtected = pathname.startsWith('/main');
  // Permite-lista: só estas páginas de /auth/* redirecionam para o hub se já
  // logado. Novas páginas de /auth/* ficam de fora por padrão, a menos que
  // adicionadas aqui deliberadamente.
  const isRedirectIfLoggedInPage = pathname === '/auth/login' || pathname === '/auth/signup';

  // ── Regra 1: rota protegida sem token → login ──────────────────────────────
  if (isProtected && !token) {
    const loginUrl = new URL('/auth/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);   // preserva destino original
    return NextResponse.redirect(loginUrl);
  }

  // ── Regra 2: já autenticado tentando acessar login/signup → hub ───────────
  if (isRedirectIfLoggedInPage && token) {
    return NextResponse.redirect(new URL('/main/hub', request.url));
  }

  // ── Regra 3: gate de perfil incompleto (/main/* exceto /main/profile) ─────
  if (isProtected && token && pathname !== '/main/profile') {
    const profileCompleteCookie = request.cookies.get('profileComplete')?.value === '1';

    if (!profileCompleteCookie) {
      const complete = await hasCompletedProfile(token);

      if (complete) {
        const response = NextResponse.next();
        response.cookies.set('profileComplete', '1', { path: '/', sameSite: 'lax', secure: true });
        return response;
      }

      const alreadySeen = request.cookies.get('profileGateSeen')?.value === '1';

      if (!alreadySeen) {
        // Primeira tentativa nesta sessão: empurrão silencioso para o cadastro.
        const response = NextResponse.redirect(new URL('/main/profile', request.url));
        response.cookies.set('profileGateSeen', '1', { path: '/', sameSite: 'lax', secure: true });
        return response;
      }

      // Já recebeu o empurrão nesta sessão e tentou sair sem completar o
      // cadastro: o cadastro é obrigatório, então encerra a sessão. Os cookies
      // são expirados na própria resposta; o AuthProvider ressincroniza o
      // estado em memória ao chegar em /auth/login.
      const response = NextResponse.redirect(new URL('/auth/login', request.url));
      for (const name of SESSION_COOKIES) {
        response.cookies.set(name, '', { path: '/', maxAge: 0 });
      }
      return response;
    }
  }

  // ── Regra 4: /main/admin sem role=admin (verificado via API) → hub ────────
  if (pathname.startsWith('/main/admin') && token) {
    const isAdmin = await isAdminToken(token);
    if (!isAdmin) {
      return NextResponse.redirect(new URL('/main/hub', request.url));
    }
  }

  return NextResponse.next();
}

// Aplica apenas nas rotas relevantes — evita rodar em assets, _next, api, etc.
export const config = {
  matcher: ['/main/:path*', '/auth/:path*'],
};
