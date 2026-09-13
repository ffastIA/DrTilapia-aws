// lib/tokens.ts
//
// Fonte única de verdade da identidade visual "Dr. Tilap-IA".
// Os valores vêm do mockup da landing page e são consumidos em dois lugares:
//   1. tailwind.config.ts  — gera os utilitários (bg-background, text-primary, ...)
//   2. styles/globals.css  — declara os mesmos valores como custom properties em :root,
//                            para o CSS Module da landing (styles/dr-tilapia.module.css)
//
// Ao alterar uma cor aqui, replique-a no bloco :root de globals.css.

export const colors = {
  /** Fundo da página. */
  background: '#f2f2f3',
  /** Superfície levemente recuada — campos de formulário, faixas internas. */
  surface: '#e9e9ea',
  /** Superfície de cards e modais. Igual ao fundo: cards se definem pela borda, não pelo tom. */
  card: '#f2f2f3',
  /** Texto principal. */
  foreground: '#1d1f20',
  /** Texto secundário — color-mix(#1d1f20 70%) achatado sobre o fundo. */
  mutedForeground: '#5d5e5f',
  /** Hairline de 1px que carrega toda a hierarquia visual — color-mix(#1d1f20 16%) sobre o fundo. */
  border: '#d0d0d1',

  /** Azul-ardósia da marca. */
  primary: '#5980a6',
  primaryHover: '#597ea3',
  primaryActive: '#416180',
  /** Texto sobre superfícies primary. */
  primaryForeground: '#f2f2f3',
  /** Tonalidade clara do accent, para realces sutis. */
  primarySoft: '#eef6ff',

  /** Anel de foco — mesmo tom do accent. */
  ring: '#5980a6',

  destructive: '#a13f3a',
  destructiveBg: '#f6e9e8',
  success: '#3f6b4a',
  successBg: '#e9f1eb',
} as const;

export type ColorToken = keyof typeof colors;
