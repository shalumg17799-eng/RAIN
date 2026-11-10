// RAIN v0.3 frontend entry.
//
// Every value the UI shows comes from the backend. The data is loaded first
// (GET /api/v3/ui/data, proof in the console), and only then is the app's
// module graph imported, so no component can render from anything local. If
// the backend cannot be reached, the app says so and renders no data at all.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { dataBase, enablePageDataLog, installConsoleHelpers, loadRainData } from './data/rain/_shared/backendData'
import { BackendUnavailable, LoadingBackendData } from './components/common/BackendDataScreens'
import { PROOF_STYLE, proof } from './core/log'

const root = createRoot(document.getElementById('root'))
const url = `${dataBase()}/data`

async function boot() {
  root.render(<LoadingBackendData url={url} />)
  try {
    await loadRainData('rain')
    const { default: App } = await import('./App.jsx')
    // From here on the console names, per page, the backend API and datasets it shows,
    // and rainQuery('CEO-S1') / rainQueries() run the personas' backend queries.
    installConsoleHelpers()
    enablePageDataLog()
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  } catch (error) {
    proof.error('%cRAIN%c No data: the backend did not deliver it, so nothing is rendered.', PROOF_STYLE.alert, '', error)
    root.render(<BackendUnavailable url={url} error={error} onRetry={boot} />)
  }
}

boot()
