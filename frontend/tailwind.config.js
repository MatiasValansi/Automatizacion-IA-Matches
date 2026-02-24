/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        eventeando: {
          dark: '#4a0e2e',      // Tu bordó característico
          purple: '#7e22ce',    // Violeta para botones
          accent: '#9333ea',    // Violeta claro para hover
        }
      },
      fontFamily: {
        serif: ['Merriweather', 'serif'],
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}