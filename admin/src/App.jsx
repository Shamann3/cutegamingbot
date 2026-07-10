import { useCallback, useEffect, useState } from 'react'
import { getAdminDisplayName } from './lib/displayName'
import { hasTelegramInitData, isAdminSessionValid, logoutAdmin } from './lib/adminClient'
import { initAdminTelegram } from './lib/telegram'
import AuthPage from './pages/AuthPage'
import PanelShell from './pages/PanelShell'
import SplashPage from './pages/SplashPage'

export default function App() {
  const [screen, setScreen] = useState('splash')
  const [displayName, setDisplayName] = useState('admin')

  useEffect(() => {
    initAdminTelegram()
    setDisplayName(getAdminDisplayName())
  }, [])

  const finishSplash = useCallback(() => {
    // Сессия действительна, если ЛИБО есть валидный локальный токен (обычно ПК),
    // ЛИБО приложение открыто из Telegram (есть initData). На телефоне Telegram
    // WebView после перезагрузки теряет токен из памяти/localStorage, но всегда
    // заново присылает initData, которым сервер аутентифицирует каждый запрос.
    // Поэтому наличие initData = действующая сессия; если это не админ —
    // сервер вернёт 403 на запросы панели, и PanelShell сам вернёт на вход.
    if (isAdminSessionValid() || hasTelegramInitData()) {
      setScreen('panel')
      return
    }
    logoutAdmin()
    setScreen('auth')
  }, [])

  const finishAuth = useCallback(() => {
    setScreen('panel')
  }, [])

  const handleLogout = useCallback(() => {
    logoutAdmin()
    setScreen('auth')
  }, [])

  if (screen === 'splash') {
    return <SplashPage displayName={displayName} onFinished={finishSplash} />
  }

  if (screen === 'auth') {
    return <AuthPage displayName={displayName} onAuthenticated={finishAuth} />
  }

  return <PanelShell onLogout={handleLogout} />
}
