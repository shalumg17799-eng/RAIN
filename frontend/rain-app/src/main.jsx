// RAIN v0.3 frontend entry.
//
// Every value the UI shows comes from the backend. The data is loaded first
// (GET /api/v4/ui/data; the console shows backend API calls only), and only then is the app's
// module graph imported, so no component can render from anything local. If
// the backend cannot be reached, the app says so and renders no data at all.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { dataBase, enablePageDataLog, installConsoleHelpers, loadRainData } from './data/rain/_shared/backendData'
import { BackendUnavailable, LoadingBackendData } from './components/common/BackendDataScreens'

const root = createRoot(document.getElementById('root'))
const url = `${dataBase()}/data`

async function boot() {
  root.render(<LoadingBackendData url={url} />)
  try {
    await loadRainData('rain')
    const { default: App } = await import('./App.jsx')
    // Console helpers that call the backend: await rainQuery('CEO-S1'), await rainQueries();
    // window.__RAIN_PAGE_DATA__ lists, per page, the backend datasets it shows (not printed).
    installConsoleHelpers()
    enablePageDataLog()
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  } catch (error) {
    root.render(<BackendUnavailable url={url} error={error} onRetry={boot} />)
  }
}

boot()
