/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      opacity: {
        8: '0.08',
        12: '0.12',
        18: '0.18',
      },
      colors: {
        ink: {
          950: '#05070c',
          900: '#090d16',
          850: '#0e1422',
          800: '#151d30',
          700: '#202b46',
          600: '#314063',
        },
        accent: {
          DEFAULT: '#7da2ff',
          soft: '#b4c9ff',
          glow: 'rgba(125, 162, 255, 0.42)',
        },
        brass: {
          DEFAULT: '#d4af6a',
          soft: '#edd29c',
          dim: 'rgba(212, 175, 106, 0.28)',
        },
      },
      fontFamily: {
        display: ['"Chakra Petch"', '"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        plate: ['"Oswald"', '"Roboto Condensed"', '"Arial Narrow"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
      fontSize: {
        display: ['clamp(2rem, 9vw, 2.75rem)', { lineHeight: '1.02', letterSpacing: '-0.03em' }],
        h1: ['1.375rem', { lineHeight: '1.18', letterSpacing: '-0.02em' }],
        h2: ['1.0625rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        body: ['0.9375rem', { lineHeight: '1.5' }],
        caption: ['0.8125rem', { lineHeight: '1.42' }],
        micro: ['0.6875rem', { lineHeight: '1.35', letterSpacing: '0.06em' }],
      },
      boxShadow: {
        lift: '0 2px 4px rgba(0,0,0,0.55), 0 14px 32px -12px rgba(0,0,0,0.9)',
        contact: '0 22px 48px -12px rgba(0,0,0,0.85)',
        hairline: 'inset 0 1px 0 rgba(255,255,255,0.09)',
        brass: '0 0 24px -6px rgba(212, 175, 106, 0.45)',
      },
      backgroundImage: {
        'mesh-dark':
          'radial-gradient(130% 70% at 50% -12%, rgba(125,162,255,0.15), transparent 58%), radial-gradient(95% 55% at 50% 108%, rgba(212,175,106,0.09), transparent 62%), radial-gradient(60% 40% at 85% 20%, rgba(168,85,247,0.05), transparent 60%)',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120%)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.92)', opacity: '0.75' },
          '70%': { transform: 'scale(1.28)', opacity: '0' },
          '100%': { transform: 'scale(1.28)', opacity: '0' },
        },
        'float-slow': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'holo-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
      animation: {
        shimmer: 'shimmer 2.6s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
        'float-slow': 'float-slow 4s ease-in-out infinite',
        'holo-shift': 'holo-shift 5s ease infinite',
      },
    },
  },
  plugins: [],
};
