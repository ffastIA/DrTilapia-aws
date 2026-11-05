// CAMINHO: frontend/app/api/auth/logout/route.ts
// Logout: revoga a sessão no Supabase (via backend) e remove os cookies.

import { NextRequest, NextResponse } from 'next/server';
import { ACCESS_COOKIE, backendUrl, clearSessionCookies } from '@/lib/serverSession';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const token = req.cookies.get(ACCESS_COOKIE)?.value;
  if (token) {
    try {
      await fetch(`${backendUrl()}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      });
    } catch {
      // Best effort: os cookies são removidos de qualquer forma.
    }
  }
  const res = NextResponse.json({ ok: true });
  clearSessionCookies(res);
  return res;
}
