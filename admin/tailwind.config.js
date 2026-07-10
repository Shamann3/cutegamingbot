/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        panel: {
          bg: '#080808',
          surface: '#0f0f0f',
          border: '#1c1c1c',
          muted: '#555555',
          accent: '#d4d4d4',
        },
      },
    },
  },
  plugins: [],
}
