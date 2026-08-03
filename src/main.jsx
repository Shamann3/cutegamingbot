import React from 'react'
import ReactDOM from 'react-dom/client'
import { SettingsProvider } from './context/SettingsContext'
import ErrorBoundary from './components/ErrorBoundary'
import ContentProtection from './components/ContentProtection'
import { initTelegramWebApp } from './lib/telegram'
import App from './App'
import './index.css'
import './styles/tabThemes.css'
import './styles/season.css'

initTelegramWebApp()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ContentProtection>
      <ErrorBoundary>
        <SettingsProvider>
          <App />
        </SettingsProvider>
      </ErrorBoundary>
    </ContentProtection>
  </React.StrictMode>,
)
