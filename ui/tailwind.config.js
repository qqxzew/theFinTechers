/** @type {import('tailwindcss').Config} */
const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Bricolage Grotesque Variable"', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'Menlo', 'monospace'],
      },
      colors: {
        paper: c('paper'),
        surface: c('surface'),
        sunken: c('sunken'),
        ink: c('ink'),
        muted: c('muted'),
        faint: c('faint'),
        accent: c('accent'),
        accentsoft: c('accentsoft'),
        amber: c('amber'),
        ambersoft: c('ambersoft'),
        // legacy aliases (resolve to the calm palette in index.css)
        line: c('line'),
        navy: c('navy'),
        teal: c('teal'),
        tealsoft: c('tealsoft'),
        warn: c('warn'),
        warnsoft: c('warnsoft'),
        bad: c('bad'),
        badsoft: c('badsoft'),
        good: c('good'),
        goodsoft: c('goodsoft'),
        violet: c('violet'),
        violetsoft: c('violetsoft'),
      },
      boxShadow: {
        rest: 'var(--sh-rest)',
        raise: 'var(--sh-raise)',
        press: 'var(--sh-press)',
        inset: 'var(--sh-inset)',
        focus: 'var(--sh-focus)',
      },
      maxWidth: {
        content: '1240px',
      },
      keyframes: {
        wire: {
          '0%': { left: '-25%' },
          '100%': { left: '100%' },
        },
        pulsebar: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(250%)' },
        },
      },
      animation: {
        pulsebar: 'pulsebar 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
