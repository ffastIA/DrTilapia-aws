// CAMINHO: frontend/app/api/auth/login/route.ts
// Login no servidor: o token vai para cookies HttpOnly e NÃO é devolvido ao browser.

import { NextRequest, NextResponse } from 'next/server';
import { backendUrl, setSessionCookies } from '@/lib/serverSession';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const body = await req.text();
  const forwarded = req.headers.get('x-forwarded-for');

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(forwarded ? { 'X-Forwarded-For': forwarded } : {}),
      },
      body,
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json({ detail: 'Serviço indisponível' }, { status: 502 });
  }

  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status });
  }

  const { access_token, refresh_token, ...safe } = data;
  const res = NextResponse.json(safe);
  setSessionCookies(res, req, { access_token, refresh_token });
  return res;
}
