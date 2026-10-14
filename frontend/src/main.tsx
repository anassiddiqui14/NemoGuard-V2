import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import './index.css'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthGateProvider } from './contexts/AuthGateContext'
import { AppRoutes } from './app/routes'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/*
     * UI MODERNIZATION (Phase 3, motion foundation): the CSS
     * `prefers-reduced-motion` rule in index.css only ever disabled CSS
     * transitions/@keyframes -- it had zero effect on the 33+ Framer
     * Motion `motion.*` components throughout the app, which animate via
     * JS transforms, not CSS. `reducedMotion="user"` makes Framer Motion
     * itself respect the OS-level accessibility preference for every
     * motion component in this subtree, with no per-component changes
     * required anywhere else in the codebase.
     */}
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <AuthGateProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthGateProvider>
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
)
