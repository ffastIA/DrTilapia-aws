/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Gera `.next/standalone` (servidor Node autocontido + só as dependências
  // realmente usadas) para a imagem Docker de produção copiar, em vez de
  // precisar do `node_modules` completo em runtime.
  output: 'standalone',
  images: {
    unoptimized: true,
  },

  // Headers de segurança em todas as respostas (SEC: clickjacking, sniffing, XSS).
  async headers() {
    const isDev = process.env.NODE_ENV !== 'production';
    // Vídeos/imagens vêm de URLs assinadas do Supabase Storage.
    const supabase = 'https://*.supabase.co';
    const csp = [
      "default-src 'self'",
      // Next.js 14 injeta scripts inline na hidratação; 'unsafe-eval' só em dev (HMR).
      `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
      "style-src 'self' 'unsafe-inline'",
      `img-src 'self' data: blob: ${supabase}`,
      `media-src 'self' blob: ${supabase}`,
      "font-src 'self' data:",
      `connect-src 'self'${isDev ? ' ws://localhost:3000' : ''}`,
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join('; ');

    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
          // Ignorado em http://; o acesso de produção é sempre HTTPS (CloudFront).
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
        ],
      },
    ];
  },

  // O proxy /api-proxy/* para o FastAPI é um route handler
  // (app/api-proxy/[...path]/route.ts): anexa o Authorization a partir do cookie
  // HttpOnly. Em produção definir BACKEND_INTERNAL_URL (variável de runtime).
};

module.exports = nextConfig;
