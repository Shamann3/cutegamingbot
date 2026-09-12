import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AdminErrorBoundary from './components/AdminErrorBoundary'
import './index.css'
// Финальный слой каскада — перебивает исторические !important из index.css.
import './styles/elite.css'
import './styles/atelier.css'
import './styles/entrance.css'
import './styles/users-ios.css'
import './styles/mobile-polish.css'
import './styles/bot-quests-phone.css'
import './styles/viewport-locks.css'
import { applyAccentToDocument, loadStoredAccent } from './lib/accentTheme'
import { applyViewportModeToDocument } from './lib/useIsDesktop'

// Подсветка до первого кадра — без вспышки дефолтного цвета
applyAccentToDocument(loadStoredAccent())
// Phone/PC до первого paint — CSS сразу берёт правильную ветку
applyViewportModeToDocument()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AdminErrorBoundary>
      <App />
    </AdminErrorBoundary>
  </React.StrictMode>,
)
