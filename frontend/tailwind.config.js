/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        'app-bg': '#050B14',
        'surface': '#0A121F',
        'surface-secondary': '#111B2C',
        'border-color': '#1E2A40',
        'text-primary': '#F1F5F9',
        'text-secondary': '#94A3B8',
        'text-muted': '#64748B',
        
        'primary': '#3B82F6',
        'primary-glow': 'rgba(59, 130, 246, 0.5)',
        
        'agent-active': '#8B5CF6',
        'healthy': '#10B981',
        'warning': '#F59E0B',
        'critical': '#EF4444',
        'info': '#0EA5E9',
      }
    },
  },
  plugins: [],
}
