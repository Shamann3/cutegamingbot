import { useCallback, useEffect, useRef, useState } from 'react'
import { getAdminDisplayName } from './lib/displayName'
import { enterAsCreator, hasTelegramInitData, isAdminSessionValid, logoutAdmin, readGroupEntry, setAdminToken } from './lib/adminClient'
import { initAdminTelegram } from './lib/telegram'
import AuthPage from './pages/AuthPage'
import PanelShell from './pages/PanelShell'
import EntranceSeal from './components/EntranceSeal'
import GatePage from './pages/GatePage'
import SecurityBoot from './components/SecurityBoot'
import { accentIsPersonal, loadStoredAccent } from './lib/accentTheme'
import { primeDashboardStats } from './lib/dashboardPrefetch'
import GroupApplyPage from './pages/GroupApplyPage'
import GroupShell from './pages/GroupShell'
import GroupKeyPage from './pages/GroupKeyPage'
import GroupResume from './pages/GroupResume'
import { prepareMemeVisit } from './lib/memeSounds'

const SPLASH_SEEN_KEY = 'epsilon_boot_splash_seen'

function shouldShowBootSplash() {
  try {
    return sessionStorage.getItem(SPLASH_SEEN_KEY) !== '1'
  } catch {
    return true
  }
}

function markBootSplashSeen() {
  try {
    sessionStorage.setItem(SPLASH_SEEN_KEY, '1')
  } catch { /* ignore */ }
}

export default function App() {
  const [screen, setScreen] = useState(() => (shouldShowBootSplash() ? 'boot' : 'gate'))
  const [displayName, setDisplayName] = useState('admin')
  const [authMode, setAuthMode] = useState('login')
  const [groupPortrait, setGroupPortrait] = useState(null)
  const [applyPreview, setApplyPreview] = useState(false)
  const [groupAgain, setGroupAgain] = useState('')
  const [channel, setChannel] = useState(null)
  const channelNext = useRef('gate')

  useEffect(() => {
    prepareMemeVisit()
    initAdminTelegram()
    setDisplayName(getAdminDisplayName())
    if (!(isAdminSessionValid() || hasTelegramInitData())) {
      logoutAdmin()
    }
  }, [])

  // Статистика главной готовится уже на визуальной загрузке —
  // к моменту входа в панель цифры есть в памяти. Экран перехода в панель
  // сотрудника (SecurityBoot kind="staff") запускает прогрев сам.
  useEffect(() => {
    if (screen !== 'boot' && screen !== 'entrance') return
    if (!(isAdminSessionValid() || hasTelegramInitData())) return
    primeDashboardStats()
  }, [screen])

  const finishAuth = useCallback(() => {
    primeDashboardStats()
    setScreen('entrance')
  }, [])

  const finishEntrance = useCallback(() => {
    setScreen('panel')
  }, [])

  const finishBootSplash = useCallback(() => {
    markBootSplashSeen()
    setScreen('gate')
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

  const openStaff = useCallback(async (fromGate) => {
    if (fromGate?.isProjectCreator) {
      try {
        const data = await enterAsCreator()
        if (!data?.token) throw new Error('Панель не открылась. Нажмите ещё раз.')
        setAdminToken(data.token)
      } catch (err) {
        if (!isAdminSessionValid()) {
          const text = String(err?.message || '')
          throw new Error(text && !/ключ/i.test(text) ? text : 'Панель не открылась. Нажмите ещё раз.')
        }
      }
      primeDashboardStats()
      openChannel('staff', 'panel')
      return
    }
    if (isAdminSessionValid() || hasTelegramInitData()) {
      primeDashboardStats()
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
    setGroupAgain('')
    if (portrait?.isProjectCreator) {
      openChannel('group', 'group')
      return
    }
    if (!readGroupEntry()) {
      setScreen('group-key')
      return
    }
    setScreen('group-resume')
  }, [openChannel])

  const passGroup = useCallback(() => openChannel('group', 'group'), [openChannel])

  const askGroupKey = useCallback((message) => {
    if (groupPortrait?.isProjectCreator) {
      openChannel('group', 'group')
      return
    }
    setGroupAgain(message || '')
    setScreen('group-key')
  }, [groupPortrait, openChannel])

  if (screen === 'boot') {
    return (
      <EntranceSeal
        displayName=""
        variant="boot"
        onFinished={finishBootSplash}
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
        onGroupApply={() => {
          setApplyPreview(false)
          setScreen('group-apply')
        }}
      />
    )
  }

  if (screen === 'group-apply') {
    return (
      <GroupApplyPage
        preview={applyPreview}
        onBack={() => {
          setApplyPreview(false)
          setScreen('gate')
        }}
      />
    )
  }

  if (screen === 'group-resume') {
    return (
      <GroupResume
        onBack={() => setScreen('gate')}
        onPassed={passGroup}
        onAskKey={askGroupKey}
      />
    )
  }

  if (screen === 'group-key') {
    return (
      <GroupKeyPage
        again={groupAgain}
        onBack={() => setScreen('gate')}
        onPassed={() => openChannel('group', 'group')}
        onPreview={() => {
          setApplyPreview(true)
          setScreen('group-apply')
        }}
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
