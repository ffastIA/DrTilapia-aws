// CAMINHO: frontend/app/api/auth/refresh/route.ts
// Usado pelo middleware: renova o par de tokens e volta para a página pedida.

import { NextRequest, NextResponse } from 'next/server';
import { REFRESH_COOKIE, clearSessionCookies, refreshTokens, setSessionCookies } from '@/lib/serverSession';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  // Só caminhos internos (evita open redirect).
  const raw = req.nextUrl.searchParams.get('redirect') || '/main/hub';
  const target = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/main/hub';

  const refreshToken = req.cookies.get(REFRESH_COOKIE)?.value;
  const tokens = refreshToken ? await refreshTokens(refreshToken) : null;

  if (!tokens) {
    const res = NextResponse.redirect(new URL('/auth/login', req.url));
    clearSessionCookies(res);
    return res;
  }
  const res = NextResponse.redirect(new URL(target, req.url));
  setSessionCookies(res, req, tokens);
  return res;
}
