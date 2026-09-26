import { useCallback, useEffect, useRef, useState } from 'react'
import { getAdminDisplayName } from './lib/displayName'
import { hasTelegramInitData, isAdminSessionValid, logoutAdmin } from './lib/adminClient'
import { initAdminTelegram } from './lib/telegram'
import AuthPage from './pages/AuthPage'
import PanelShell from './pages/PanelShell'
import SplashPage from './pages/SplashPage'
import EntranceSeal from './components/EntranceSeal'
import GatePage from './pages/GatePage'
import SecurityBoot from './components/SecurityBoot'
import { accentIsPersonal, loadStoredAccent } from './lib/accentTheme'
import GroupApplyPage from './pages/GroupApplyPage'
import GroupShell from './pages/GroupShell'
import GroupKeyPage from './pages/GroupKeyPage'

export default function App() {
  const [screen, setScreen] = useState('splash')
  const [displayName, setDisplayName] = useState('admin')
  const [authMode, setAuthMode] = useState('login')
  const [groupPortrait, setGroupPortrait] = useState(null)
  const [channel, setChannel] = useState(null)
  const channelNext = useRef('gate')

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
    if (!(isAdminSessionValid() || hasTelegramInitData())) {
      logoutAdmin()
    }
    setScreen('boot')
  }, [])

  const finishAuth = useCallback(() => {
    // После успешного логина — короткая печать власти/защиты, затем панель.
    setScreen('entrance')
  }, [])

  const finishEntrance = useCallback(() => {
    setScreen('panel')
  }, [])

  const handleLogout = useCallback(() => {
    logoutAdmin()
    setScreen('gate')
  }, [])

  const openChannel = useCallback((kind, next) => {
    channelNext.current = next
    setChannel(kind)
    setScreen('channel')
  }, [])

  const openStaff = useCallback(() => {
    // Как раньше: из Telegram initData уже есть сессия.
    // Ключ спрашиваем, только если открыли панель без него.
    if (isAdminSessionValid() || hasTelegramInitData()) {
      openChannel('staff', 'panel')
      return
    }
    setAuthMode('login')
    setScreen('auth')
  }, [openChannel])

  const openStaffApply = useCallback(() => {
    setAuthMode('register')
    setScreen('auth')
  }, [])

  const openGroup = useCallback((portrait) => {
    setGroupPortrait(portrait || null)
    if (portrait?.isOwner || hasTelegramInitData() || isAdminSessionValid()) {
      openChannel('group', 'group')
      return
    }
    setScreen('group-key')
  }, [openChannel])

  if (screen === 'splash') {
    return <SplashPage displayName={displayName} onFinished={finishSplash} />
  }

  if (screen === 'boot') {
    return (
      <SecurityBoot
        personal={accentIsPersonal(loadStoredAccent())}
        kind="gate"
        onDone={() => setScreen('gate')}
      />
    )
  }

  if (screen === 'channel' && channel) {
    return (
      <SecurityBoot
        personal={accentIsPersonal(loadStoredAccent())}
        kind={channel}
        onDone={() => setScreen(channelNext.current)}
      />
    )
  }

  if (screen === 'gate') {
    return (
      <GatePage
        onStaffEnter={openStaff}
        onStaffApply={openStaffApply}
        onGroupEnter={openGroup}
        onGroupApply={() => setScreen('group-apply')}
      />
    )
  }

  if (screen === 'group-apply') {
    return <GroupApplyPage onBack={() => setScreen('gate')} />
  }

  if (screen === 'group-key') {
    return (
      <GroupKeyPage
        onBack={() => setScreen('gate')}
        onPassed={() => openChannel('group', 'group')}
      />
    )
  }

  if (screen === 'group') {
    return (
      <GroupShell
        portrait={groupPortrait}
        onLeave={() => setScreen('gate')}
        onStaffApply={openStaffApply}
      />
    )
  }

  if (screen === 'auth') {
    return (
      <AuthPage
        displayName={displayName}
        initialMode={authMode}
        fortress
        onBack={() => setScreen('gate')}
        onAuthenticated={finishAuth}
      />
    )
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

  return <PanelShell onLogout={handleLogout} onChangeDoor={() => setScreen('gate')} />
}
