/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      spacing: {
        '4.5': '1.125rem',
      },
      colors: {
        bg: {
          DEFAULT: '#0B1020',
          deep: '#070A16',
        },
        card: {
          DEFAULT: '#151E30',
          light: '#1B2740',
          border: '#223252',
        },
        primary: {
          DEFAULT: '#4DA3FF',
          dim: '#3A7ACC',
        },
        cyan: {
          DEFAULT: '#63D9FF',
        },
        muted: '#8A9AB8',
      },
      fontFamily: {
        sans: ['"Space Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(77,163,255,0.25), 0 8px 30px -8px rgba(77,163,255,0.35)',
        'glow-lg': '0 0 0 1px rgba(99,217,255,0.3), 0 20px 60px -15px rgba(77,163,255,0.45)',
        'glow-sm': '0 0 20px rgba(77,163,255,0.25)',
      },
      keyframes: {
        'fade-slide-up': {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.55', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.06)' },
        },
        'ring-spin': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        wave: {
          '0%, 100%': { transform: 'scaleY(0.3)' },
          '50%': { transform: 'scaleY(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-slide-up': 'fade-slide-up 0.6s ease-out both',
        'pulse-glow': 'pulse-glow 2.4s ease-in-out infinite',
        'ring-spin': 'ring-spin 3s linear infinite',
        'ring-spin-slow': 'ring-spin 6s linear infinite',
        wave: 'wave 1.2s ease-in-out infinite',
        shimmer: 'shimmer 2.5s linear infinite',
      },
    },
  },
  plugins: [],
}
