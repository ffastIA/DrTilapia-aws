// CAMINHO: frontend/app/layout.tsx

import type { Metadata } from 'next';
import { barlow, barlowCondensed } from '@/lib/fonts';
import '@/styles/globals.css';
import AuthProvider from '@/components/AuthProvider';

export const metadata: Metadata = {
  title: 'Dr. Tilápia 2.0 - Consultoria de IA',
  description: 'Seu assistente inteligente para piscicultura e aquacultura.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${barlow.variable} ${barlowCondensed.variable} font-body`}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}