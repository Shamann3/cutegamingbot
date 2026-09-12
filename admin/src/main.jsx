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
import { applyAccentToDocument, loadStoredAccent } from './lib/accentTheme'

// Подсветка до первого кадра — без вспышки дефолтного цвета
applyAccentToDocument(loadStoredAccent())

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AdminErrorBoundary>
      <App />
    </AdminErrorBoundary>
  </React.StrictMode>,
)
