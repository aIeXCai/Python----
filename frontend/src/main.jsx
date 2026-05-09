import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

// Preload Monaco locally instead of CDN (skipped in test env)
if (import.meta.env.MODE !== 'test') {
  import('./monaco-setup.js')
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
