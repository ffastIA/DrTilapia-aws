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

  // O proxy /api-proxy/* para o FastAPI é um route handler
  // (app/api-proxy/[...path]/route.ts): anexa o Authorization a partir do cookie
  // HttpOnly. Em produção definir BACKEND_INTERNAL_URL (variável de runtime).
};

module.exports = nextConfig;
