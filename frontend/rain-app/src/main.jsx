// RAIN — Rural Health AI Infrastructure for Nevada (University of Nevada, Reno)
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { installFetchLogger } from './utils/dataLog.js'

// Log every RAIN API request so the console shows which data is live.
installFetchLogger(import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000')

// Dev-only: cross-check persona chips/signals/flows for broken string links.
if (import.meta.env.DEV) {
  import('./data/validatePersonaData.js').then((m) => m.reportPersonaData())
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
