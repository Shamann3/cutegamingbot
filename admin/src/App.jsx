import { useCallback, useEffect, useRef, useState } from 'react'
import { getAdminDisplayName } from './lib/displayName'
import { enterAsCreator, hasTelegramInitData, isAdminSessionValid, logoutAdmin, readGroupEntry, setAdminToken } from './lib/adminClient'
import { initAdminTelegram } from './lib/telegram'
import AuthPage from './pages/AuthPage'
import PanelShell from './pages/PanelShell'
import EntranceSeal from './components/EntranceSeal'
import EntryRite from './components/EntryRite'
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

function askedDoor() {
  try {
    return new URLSearchParams(window.location.search).get('go') || ''
  } catch {
    return ''
  }
}

function doorScreen(go) {
  if (go === 'group-apply') return 'group-apply'
  if (go === 'group-enter') return readGroupEntry() ? 'group-resume' : 'group-key'
  if (go === 'staff-register' || go === 'staff-enter') return 'auth'
  return 'gate'
}

export default function App() {
  const door = askedDoor()
  const [screen, setScreen] = useState(() => (shouldShowBootSplash() ? 'boot' : doorScreen(door)))
  const [displayName, setDisplayName] = useState('admin')
  const [authMode, setAuthMode] = useState(door === 'staff-register' ? 'register' : 'login')
  const [groupPortrait, setGroupPortrait] = useState(null)
  const [applyPreview, setApplyPreview] = useState(false)
  const [groupAgain, setGroupAgain] = useState('')
  const [channel, setChannel] = useState(null)
  const [rite, setRite] = useState('')
  const channelNext = useRef('gate')
  const riteNext = useRef('')

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

  const finishEntrance = useCallback(() => {
    setScreen('panel')
  }, [])

  const finishBootSplash = useCallback(() => {
    markBootSplashSeen()
    const go = askedDoor()
    if (go === 'staff-register') setAuthMode('register')
    if (go === 'staff-enter') setAuthMode('login')
    setScreen(doorScreen(go))
  }, [])

  const handleLogout = useCallback((reason) => {
    logoutAdmin()
    if (String(reason || '').includes('другое устройство')) {
      setAuthMode('login')
      setScreen('auth')
      return
    }
    setScreen('gate')
  }, [])

  const openChannel = useCallback((kind, next) => {
    channelNext.current = next
    setChannel(kind)
    setScreen('channel')
  }, [])

  const openAfterRite = useCallback((digits, next) => {
    const code = String(digits || '').replace(/\D/g, '').slice(0, 6)
    if (code.length !== 6) {
      if (next === 'entrance') setScreen('entrance')
      else openChannel('group', 'group')
      return
    }
    riteNext.current = next
    setRite(code)
  }, [openChannel])

  const finishAuth = useCallback((digits) => {
    primeDashboardStats()
    openAfterRite(digits, 'entrance')
  }, [openAfterRite])

  const finishRite = useCallback(() => {
    const next = riteNext.current
    riteNext.current = ''
    setRite('')
    if (next === 'entrance') setScreen('entrance')
    else openChannel('group', 'group')
  }, [openChannel])

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
    if (isAdminSessionValid()) {
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

  const passGroup = useCallback((digits) => {
    openAfterRite(digits, 'group')
  }, [openAfterRite])

  const openGroupApply = useCallback(() => {
    setApplyPreview(false)
    setScreen('group-apply')
  }, [])

  const askGroupKey = useCallback((message) => {
    if (groupPortrait?.isProjectCreator) {
      openChannel('group', 'group')
      return
    }
    setGroupAgain(message || '')
    setScreen('group-key')
  }, [groupPortrait, openChannel])

  if (rite) {
    return <EntryRite digits={rite} onDone={finishRite} />
  }

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
        onGroupApply={openGroupApply}
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
        onPassed={passGroup}
        onApply={openGroupApply}
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
