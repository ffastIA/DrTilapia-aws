// CAMINHO: frontend/app/api-proxy/[...path]/route.ts
// Proxy para o backend FastAPI. Anexa o Authorization a partir do cookie HttpOnly
// (o browser nunca vê o token) e renova o token expirando antes de repassar.
// Substitui o rewrite de next.config.js.

import { NextRequest, NextResponse } from 'next/server';
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  backendUrl,
  forbiddenCrossOrigin,
  isExpiring,
  isSameOriginRequest,
  refreshTokens,
  setSessionCookies,
} from '@/lib/serverSession';

export const dynamic = 'force-dynamic';

// Cabeçalhos que não devem ser repassados em nenhuma direção.
const HOP_BY_HOP = ['connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'host', 'content-length'];

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  if (!isSameOriginRequest(req)) return forbiddenCrossOrigin();

  let accessToken = req.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE)?.value;
  let renewed: { access_token: string; refresh_token: string } | null = null;

  if (refreshToken && (!accessToken || isExpiring(accessToken))) {
    renewed = await refreshTokens(refreshToken);
    if (renewed) accessToken = renewed.access_token;
  }

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    // O Authorization vem SÓ do cookie; cookies do browser não vão ao backend.
    if (HOP_BY_HOP.includes(k) || k === 'authorization' || k === 'cookie') return;
    headers.set(key, value);
  });
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);

  const url = `${backendUrl()}/${params.path.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;
  const hasBody = !['GET', 'HEAD'].includes(req.method);

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      // `duplex` é exigido pelo Node para corpo em streaming (ausente nos tipos DOM).
      ...(hasBody ? { duplex: 'half' } : {}),
      redirect: 'manual',
      cache: 'no-store',
      signal: AbortSignal.timeout(300_000),
    } as RequestInit);
  } catch {
    return NextResponse.json({ detail: 'Serviço indisponível' }, { status: 502 });
  }

  const resHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    // fetch já descomprime o corpo; não repassar content-encoding/length.
    if (HOP_BY_HOP.includes(k) || k === 'content-encoding') return;
    resHeaders.set(key, value);
  });

  const res = new NextResponse(upstream.body, { status: upstream.status, headers: resHeaders });
  if (renewed) setSessionCookies(res, req, renewed);
  return res;
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as OPTIONS };
