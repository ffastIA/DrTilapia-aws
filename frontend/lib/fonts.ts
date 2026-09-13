// lib/fonts.ts
import { Barlow, Barlow_Condensed } from 'next/font/google';

// Fonte de corpo do sistema "Dr. Tilap-IA" (aplicada globalmente).
export const barlow = Barlow({
  subsets: ['latin'],
  variable: '--font-barlow',
  weight: ['400', '500', '700'],
  display: 'swap',
});

// Fonte de títulos do sistema "Dr. Tilap-IA" (uppercase, peso 600).
export const barlowCondensed = Barlow_Condensed({
  subsets: ['latin'],
  variable: '--font-barlow-condensed',
  weight: ['400', '600'],
  display: 'swap',
});
