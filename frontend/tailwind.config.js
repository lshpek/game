/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // Tailwind's default opacity scale has no 8/12 - the UI design uses them.
      opacity: {
        8: '0.08',
        12: '0.12',
        18: '0.18',
      },
      colors: {
        ink: {
          950: '#05060c',
          900: '#0a0c16',
          850: '#0e1120',
          800: '#141829',
          700: '#1d2238',
          600: '#2a3050',
        },
        accent: {
          DEFAULT: '#7c5cff',
          soft: '#a78bfa',
          glow: 'rgba(124, 92, 255, 0.55)',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 32px rgba(124, 92, 255, 0.35)',
        card: '0 12px 40px rgba(0, 0, 0, 0.45)',
      },
      backgroundImage: {
        'mesh-dark':
          'radial-gradient(circle at 20% 0%, rgba(124,92,255,0.20), transparent 45%), radial-gradient(circle at 90% 10%, rgba(34,211,238,0.14), transparent 40%), radial-gradient(circle at 50% 100%, rgba(244,63,94,0.12), transparent 50%)',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.7' },
          '70%': { transform: 'scale(1.25)', opacity: '0' },
          '100%': { transform: 'scale(1.25)', opacity: '0' },
        },
      },
      animation: {
        shimmer: 'shimmer 2.4s infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
      },
    },
  },
  plugins: [],
};
