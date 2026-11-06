// CAMINHO: frontend/lib/serverSession.ts
// Helpers SÓ de servidor (route handlers) para a sessão em cookies HttpOnly (SEC-02).
// O access/refresh token nunca chega ao JavaScript do navegador.

import type { NextRequest, NextResponse } from 'next/server';

export const ACCESS_COOKIE = 'accessToken';
export const REFRESH_COOKIE = 'refreshToken';

export const backendUrl = () =>
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';

/** Cookie Secure é descartado pelo browser em http:// — segue o protocolo real da requisição. */
export function isSecureRequest(req: NextRequest): boolean {
  return req.headers.get('x-forwarded-proto') === 'https' || req.nextUrl.protocol === 'https:';
}

export function setSessionCookies(
  res: NextResponse,
  req: NextRequest,
  tokens: { access_token: string; refresh_token?: string | null },
) {
  const base = {
    httpOnly: true,
    secure: isSecureRequest(req),
    sameSite: 'lax' as const,
    path: '/',
  };
  res.cookies.set(ACCESS_COOKIE, tokens.access_token, base);
  if (tokens.refresh_token) res.cookies.set(REFRESH_COOKIE, tokens.refresh_token, base);
}

export function clearSessionCookies(res: NextResponse) {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, 'user', 'profileGateSeen', 'profileComplete']) {
    res.cookies.set(name, '', { path: '/', maxAge: 0 });
  }
}

/** Lê `exp` (segundos) do JWT sem validar assinatura — só para decidir se renova. */
export function jwtExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function isExpiring(token: string, marginSeconds = 30): boolean {
  const exp = jwtExpiry(token);
  return exp === null || exp - marginSeconds <= Math.floor(Date.now() / 1000);
}

export async function refreshTokens(
  refreshToken: string,
): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const r = await fetch(`${backendUrl()}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: 'no-store',
    });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/**
 * Defesa contra CSRF: a sessão vai em cookie, então requisições que alteram dados
 * só valem se partirem do próprio site.
 *
 * - `Sec-Fetch-Site` (enviado por todos os navegadores atuais) deve ser
 *   `same-origin` (ou `none`, ação direta do usuário). `cross-site`/`same-site`
 *   (inclui subdomínios irmãos) são recusados.
 * - Sem esse header, vale o `Origin`: precisa estar em ALLOWED_ORIGINS (lista
 *   separada por vírgulas, variável de runtime) ou coincidir com o host da requisição.
 * - Sem nenhum dos dois não há navegador envolvido (curl etc.): sem risco de CSRF.
 */
export function isSameOriginRequest(req: NextRequest): boolean {
  const safeMethods = ['GET', 'HEAD', 'OPTIONS'];
  if (safeMethods.includes(req.method)) return true;

  const fetchSite = req.headers.get('sec-fetch-site');
  if (fetchSite) return fetchSite === 'same-origin' || fetchSite === 'none';

  const origin = req.headers.get('origin');
  if (!origin) return true;

  const allowed = (process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((o) => o.trim().replace(/\/$/, ''))
    .filter(Boolean);
  if (allowed.length > 0) return allowed.includes(origin.replace(/\/$/, ''));

  try {
    const host = req.headers.get('x-forwarded-host') || req.headers.get('host');
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export const forbiddenCrossOrigin = () =>
  Response.json({ detail: 'Origem não permitida' }, { status: 403 });
