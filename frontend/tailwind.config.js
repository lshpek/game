/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // Tailwind's default opacity scale has no 8/12/18 - the design system uses them.
      opacity: {
        8: '0.08',
        12: '0.12',
        18: '0.18',
      },
      colors: {
        /*
         * Ink is the whole surface family: near-black, very slightly blue, so a white
         * plate on it reads as the brightest object in the room. Everything else in the
         * UI is deliberately low-contrast against it.
         */
        ink: {
          950: '#05070c',
          900: '#0a0d16',
          850: '#0f1320',
          800: '#161b2c',
          700: '#212840',
          600: '#313a56',
        },
        /*
         * A single restrained azure. It marks *interaction*, never rarity: rarity has its
         * own colours (see RARITY_COLORS) and the two must never be confused.
         */
        accent: {
          DEFAULT: '#8aa7ff',
          soft: '#b9c9ff',
          glow: 'rgba(138, 167, 255, 0.35)',
        },
        /*
         * Brass. The one warm note in the product: hairline trim on premium surfaces and
         * the value read-out. Used at low coverage so it stays an accent, not a theme.
         */
        brass: {
          DEFAULT: '#c9a86b',
          soft: '#e0c493',
          dim: 'rgba(201, 168, 107, 0.28)',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        /*
         * Plate lettering. A condensed grotesque is what real registration plates use,
         * and it is what makes the rendered object read as metal rather than as a label.
         */
        plate: ['"Arial Narrow"', '"Roboto Condensed"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
      /*
       * One scale, used everywhere. The previous UI picked an arbitrary `text-[10px]`
       * with `tracking-[0.3em]` per component, which is what made it read as sparse and
       * unresolved; these six steps are the whole system.
       */
      fontSize: {
        display: ['clamp(2rem, 9vw, 2.75rem)', { lineHeight: '1.02', letterSpacing: '-0.03em' }],
        h1: ['1.375rem', { lineHeight: '1.18', letterSpacing: '-0.02em' }],
        h2: ['1.0625rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        body: ['0.9375rem', { lineHeight: '1.5' }],
        caption: ['0.8125rem', { lineHeight: '1.42' }],
        micro: ['0.6875rem', { lineHeight: '1.35', letterSpacing: '0.06em' }],
      },
      boxShadow: {
        /*
         * Physical shadows: a contact shadow that touches the surface plus a long soft
         * falloff. The old `glow` (a 32px coloured halo) was the single clearest reason
         * the app looked like a crypto dashboard, so it is gone.
         */
        lift: '0 1px 2px rgba(0,0,0,0.5), 0 12px 28px -14px rgba(0,0,0,0.85)',
        contact: '0 18px 44px -12px rgba(0,0,0,0.75)',
        hairline: 'inset 0 1px 0 rgba(255,255,255,0.07)',
      },
      backgroundImage: {
        /*
         * One soft overhead light instead of the old three-colour neon mesh. The scene
         * should look like a dim vitrine, not a dashboard.
         */
        'mesh-dark':
          'radial-gradient(120% 65% at 50% -10%, rgba(138,167,255,0.10), transparent 60%), radial-gradient(90% 50% at 50% 110%, rgba(201,168,107,0.06), transparent 65%)',
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
