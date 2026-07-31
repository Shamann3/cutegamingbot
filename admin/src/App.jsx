import { useCallback, useEffect, useState } from 'react'
import { getAdminDisplayName } from './lib/displayName'
import { hasTelegramInitData, isAdminSessionValid, logoutAdmin } from './lib/adminClient'
import { initAdminTelegram } from './lib/telegram'
import AuthPage from './pages/AuthPage'
import PanelShell from './pages/PanelShell'
import SplashPage from './pages/SplashPage'
import EntranceSeal from './components/EntranceSeal'

export default function App() {
  const [screen, setScreen] = useState('splash')
  const [displayName, setDisplayName] = useState('admin')

  useEffect(() => {
    initAdminTelegram()
    setDisplayName(getAdminDisplayName())
  }, [])

  const finishSplash = useCallback(() => {
    // Печать (splash) уже показана всем — и тем, кто пойдёт на регистрацию,
    // и тем, у кого есть сессия. Дальше — auth или panel.
    if (isAdminSessionValid() || hasTelegramInitData()) {
      setScreen('panel')
      return
    }
    logoutAdmin()
    setScreen('auth')
  }, [])

  const finishAuth = useCallback(() => {
    // После успешного логина/подтверждения — та же печать, затем панель.
    setScreen('entrance')
  }, [])

  const finishEntrance = useCallback(() => {
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

  if (screen === 'entrance') {
    return (
      <EntranceSeal
        displayName={displayName}
        variant="login"
        onFinished={finishEntrance}
      />
    )
  }

  return <PanelShell onLogout={handleLogout} />
}
