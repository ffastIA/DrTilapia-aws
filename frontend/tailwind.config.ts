import type { Config } from 'tailwindcss';
import { colors } from './lib/tokens';

const config: Config = {
  content: [
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // Barlow Condensed 600 uppercase para títulos, Barlow 400 para corpo.
        heading: ['var(--font-barlow-condensed)', 'system-ui', 'sans-serif'],
        body: ['var(--font-barlow)', 'system-ui', 'sans-serif'],
      },
      // Hex literais (não var()) para que os modificadores de opacidade
      // do Tailwind — bg-destructive/10, border-primary/30 — continuem funcionando.
      colors: {
        background: colors.background,
        surface: colors.surface,
        card: colors.card,
        foreground: colors.foreground,
        'muted-foreground': colors.mutedForeground,
        border: colors.border,
        primary: {
          DEFAULT: colors.primary,
          hover: colors.primaryHover,
          active: colors.primaryActive,
          foreground: colors.primaryForeground,
          soft: colors.primarySoft,
        },
        ring: colors.ring,
        destructive: {
          DEFAULT: colors.destructive,
          bg: colors.destructiveBg,
        },
        success: {
          DEFAULT: colors.success,
          bg: colors.successBg,
        },
      },
      borderRadius: {
        // O design é quadrado por escolha: .btn e .input forçam 0 explicitamente.
        DEFAULT: '0',
      },
      spacing: {
        // Grade de 24px da landing.
        leading: '24px',
        half: '12px',
        edge: 'clamp(20px, 5vw, 72px)',
      },
      maxWidth: {
        wrap: '1200px',
        measure: '60ch',
      },
      screens: {
        // Os três breakpoints max-width da landing, expostos como variantes.
        'lp-lg': { max: '880px' },
        'lp-md': { max: '720px' },
        'lp-sm': { max: '560px' },
      },
    },
  },
  plugins: [],
};

export default config;
