import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthGateProvider } from './contexts/AuthGateContext'
import { AppRoutes } from './app/routes'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthGateProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthGateProvider>
    </ThemeProvider>
  </StrictMode>,
)
