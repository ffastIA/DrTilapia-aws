/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    unoptimized: true,
  },

  /**
   * Proxy reverso para o backend FastAPI.
   *
   * Requests de /api-proxy/* são repassadas para http://localhost:8000/*
   * pelo servidor Next.js. O browser nunca vê um request cross-origin,
   * então não há CORS preflight — elimina completamente os problemas de
   * CORS para FormData/multipart e outros requests com headers customizados.
   *
   * Em produção: definir BACKEND_INTERNAL_URL no ambiente de deploy
   * (ex: http://backend:8000 dentro de docker-compose, ou URL interna).
   */
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      'http://localhost:8000';

    return [
      {
        source: '/api-proxy/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
