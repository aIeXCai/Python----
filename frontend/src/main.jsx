import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

async function bootstrap() {
  // Monaco must be configured before any <Editor> mounts.  If this import is
  // left un-awaited, @monaco-editor/react can fall back to its public CDN,
  // which is unavailable on an offline classroom LAN.
  if (import.meta.env.MODE !== 'test') {
    await import('./monaco-setup.js')
  }

  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

bootstrap()
