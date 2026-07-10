/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './panel/index.html', './src/**/*.{js,jsx}', './admin/src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'system-ui', 'sans-serif'],
        panel: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        farm: {
          grass: '#4ade80',
          soil: '#8B4513',
          soilDark: '#5c2e0a',
          sky: '#87CEEB',
        },
        panel: {
          bg: '#0a0a0f',
          surface: '#12121a',
          border: '#1e1e2e',
          muted: '#6b7280',
          accent: '#6366f1',
        },
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'float-delayed': 'float 6s ease-in-out 2s infinite',
        'pulse-soft': 'pulse-soft 3s ease-in-out infinite',
        'cloud': 'cloud 25s linear infinite',
        'water-drop': 'water-drop 0.7s ease-in forwards',
        'water-splash': 'water-splash 1.2s ease-out forwards',
        'slide-up': 'slide-up 0.35s ease-out forwards',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: 0.6 },
          '50%': { opacity: 1 },
        },
        cloud: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120vw)' },
        },
        'water-drop': {
          '0%': { transform: 'translateY(0) scale(1)', opacity: 1 },
          '100%': { transform: 'translateY(72px) scale(0.5)', opacity: 0 },
        },
        'water-splash': {
          '0%': { opacity: 0.5 },
          '50%': { opacity: 0.35 },
          '100%': { opacity: 0 },
        },
        'slide-up': {
          '0%': { transform: 'translateY(24px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
      },
    },
  },
  plugins: [],
}
