/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'monospace'],
      },
      keyframes: {
        wire: {
          '0%': { left: '-25%' },
          '100%': { left: '100%' },
        },
      },
      colors: {
        paper: 'rgb(var(--paper) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        navy: 'rgb(var(--navy) / <alpha-value>)',
        teal: 'rgb(var(--teal) / <alpha-value>)',
        tealsoft: 'rgb(var(--tealsoft) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        warnsoft: 'rgb(var(--warnsoft) / <alpha-value>)',
        bad: 'rgb(var(--bad) / <alpha-value>)',
        badsoft: 'rgb(var(--badsoft) / <alpha-value>)',
        good: 'rgb(var(--good) / <alpha-value>)',
        goodsoft: 'rgb(var(--goodsoft) / <alpha-value>)',
        violet: 'rgb(var(--violet) / <alpha-value>)',
        violetsoft: 'rgb(var(--violetsoft) / <alpha-value>)',
      },
    },
  },
  plugins: [],
};
