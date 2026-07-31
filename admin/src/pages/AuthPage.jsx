import { useCallback, useEffect, useRef, useState } from 'react'
import {
  confirmAdminRegistration,
  fetchAdminAuthStatus,
  fetchAdminMe,
  hasTelegramInitData,
  loginAdmin,
  setAdminToken,
  startAdminRegistration,
  submitAdminApplication,
  takeSessionEndedReason,
} from '../lib/adminClient'
import AuthTabs from '../components/AuthTabs'
import LoginForm from '../components/LoginForm'
import PanelBackdrop from '../components/PanelBackdrop'
import GoldBackdrop from '../components/GoldBackdrop'
import RegisterForm from '../components/RegisterForm'
import ApplicationForm from '../components/ApplicationForm'
import EpsilonLogo from '../components/EpsilonLogo'

function slideClassForMode(nextMode) {
  return nextMode === 'register' ? 'auth-form-from-right' : 'auth-form-from-left'
}

// Метка сборки — временная, чтобы точно понять, свежий ли код загрузился на телефоне.
const BUILD_TAG = 'v9-ident'

export default function AuthPage({ displayName, onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [slideClass, setSlideClass] = useState('auth-form-from-left')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [success, setSuccess] = useState('')
  const [setup, setSetup] = useState(null)
  const [registered, setRegistered] = useState(false)
  // 'key' | 'totp' | 'application' | 'waiting'
  const [regStage, setRegStage] = useState('key')
  const [keyType, setKeyType] = useState(null)
  const modeRef = useRef('login')

  const switchMode = useCallback((nextMode) => {
    if (nextMode !== modeRef.current) {
      setSlideClass(slideClassForMode(nextMode))
    }
    modeRef.current = nextMode
    setMode(nextMode)
  }, [])

  useEffect(() => {
    let cancelled = false

    // Если сюда вернулись из-за разрыва сессии — покажем причину красным (заметно),
    // чтобы точно понять, какой запрос и почему вернул 401.
    const endedReason = takeSessionEndedReason()
    if (endedReason) setError(endedReason)

    fetchAdminAuthStatus()
      .then((status) => {
        if (cancelled) return
        setRegistered(Boolean(status.registered))
        // Кандидат с уже поданной заявкой — сразу экран ожидания в «Регистрации».
        if (status.status === 'pending' && status.applicationStatus === 'pending') {
          setRegStage('waiting')
        }
      })
      .catch(() => {
        // Telegram initData может быть недоступен вне бота
      })

    return () => {
      cancelled = true
    }
  }, [])

  const handleLogin = useCallback(
    async ({ loginKey, totp }) => {
      if (!hasTelegramInitData() && !(import.meta.env.DEV && import.meta.env.VITE_DEV_USER_ID)) {
        setError('Откройте панель через admin-бота в Telegram (нужна сессия Telegram).')
        return
      }

      setError('')
      setInfo('')
      setLoading(true)

      try {
        const data = await loginAdmin(loginKey, totp)
        if (!data.token) {
          throw new Error('Сервер не выдал токен сессии. Обновите панель и попробуйте снова.')
        }
        setAdminToken(data.token)

        // Проверяем сессию ДО входа в панель: делаем реальный запрос /auth/me.
        // Если он не пройдёт — покажем причину прямо здесь, а не «моргнём»
        // панелью и не выкинем обратно на вход. Так вход стабилен на любом
        // устройстве, а ошибки всегда видны пользователю.
        await fetchAdminMe()

        setInfo('')
        setSuccess('Подключение успешно')
        // Короткая пауза на success-toast, затем печать входа (EntranceSeal).
        window.setTimeout(() => onAuthenticated(), 320)
      } catch (err) {
        setSuccess('')
        const status = err?.status ? ` [код ${err.status}]` : ''
        setError((err.message || 'Не удалось войти') + status)
      } finally {
        setLoading(false)
      }
    },
    [onAuthenticated],
  )

  const handleRegisterStart = useCallback(async (inviteKey, options = {}) => {
    if (options?.reset) {
      setSetup(null)
      setKeyType(null)
      setRegStage('key')
      setError('')
      setInfo('')
      return
    }

    if (registered) {
      switchMode('login')
      setInfo('Аккаунт уже зарегистрирован. Войдите во вкладке «Вход».')
      return
    }

    setError('')
    setInfo('')
    setLoading(true)

    try {
      const data = await startAdminRegistration(inviteKey)
      setSetup(data)
      setKeyType(data.keyType || 'staff')
      setRegStage('totp')
      setInfo('')
    } catch (err) {
      setError(err.message || 'Не удалось начать регистрацию')
    } finally {
      setLoading(false)
    }
  }, [registered, switchMode])

  const handleRegisterConfirm = useCallback(
    async (totp) => {
      if (!setup?.setupToken) return

      setError('')
      setLoading(true)

      try {
        const data = await confirmAdminRegistration(setup.setupToken, totp)
        const type = data.keyType || keyType
        setSetup(null)

        if (type === 'staff' || data.requiresApplication) {
          // Кандидат — переходим к анкете.
          setRegStage('application')
          setInfo('')
          setError('')
          return
        }

        // Владелец — аккаунт активен, идём ко входу.
        setAdminToken('')
        setRegistered(true)
        setRegStage('key')
        switchMode('login')
        setInfo('Регистрация завершена. Войдите тем же ключом и кодом из приложения.')
      } catch (err) {
        setError(err.message || 'Не удалось завершить регистрацию')
        setInfo('')
      } finally {
        setLoading(false)
      }
    },
    [setup, keyType, switchMode],
  )

  const handleApplicationSubmit = useCallback(async (payload) => {
    setError('')
    setInfo('')
    setLoading(true)

    try {
      await submitAdminApplication(payload)
      setRegistered(true)
      setRegStage('waiting')
    } catch (err) {
      setError(err.message || 'Не удалось отправить заявку')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleTabChange = useCallback(
    (nextMode) => {
      switchMode(nextMode)
      setError('')
      setSuccess('')
      if (nextMode === 'register' && regStage !== 'waiting') {
        setSetup(null)
        setRegStage('key')
      }
    },
    [switchMode, regStage],
  )

  const formKey =
    mode === 'register'
      ? regStage === 'application' || regStage === 'waiting'
        ? `register-${regStage}`
        : 'register-main'
      : mode

  function renderRegister() {
    if (regStage === 'waiting') {
      return (
        <div className="auth-form">
          <p className="auth-message auth-message-info">
            Заявка отправлена. Ожидайте — владелец рассмотрит её.
            Вход откроется после одобрения.
          </p>
        </div>
      )
    }

    if (regStage === 'application') {
      return (
        <ApplicationForm
          onSubmit={handleApplicationSubmit}
          loading={loading}
          error={error}
          info={info}
        />
      )
    }

    return (
      <RegisterForm
        onStart={handleRegisterStart}
        onConfirm={handleRegisterConfirm}
        onEditKey={() => {
          setError('')
          setInfo('')
        }}
        loading={loading}
        error={error}
        info={info}
        setup={setup}
        registered={registered}
      />
    )
  }

  return (
    <div className="auth-screen">
      <GoldBackdrop />
      <PanelBackdrop active />

      <div className="auth-card">
        <header className="auth-header">
          <div className="auth-logo-wrap">
            <EpsilonLogo className="auth-logo" size="lg" alt="Cute Epsilon" />
          </div>
          <h1 className="auth-title">Panel</h1>
          <p className="auth-subtitle">Защищённый доступ</p>
        </header>

        <AuthTabs mode={mode} onChange={handleTabChange} />

        {success && (
          <p className="auth-message auth-message-success auth-success-pop" role="status">
            <span className="auth-success-check">✓</span>
            {success}
          </p>
        )}

        <div className="auth-form-viewport">
          <div
            className={`auth-form-wrap ${slideClass}`}
            key={formKey}
          >
            {mode === 'login' ? (
              <LoginForm
                onSubmit={handleLogin}
                loading={loading}
                error={error}
                info={info}
              />
            ) : (
              renderRegister()
            )}
          </div>
        </div>

        <div className="auth-salute" aria-hidden="true">
          <span className="auth-salute-line" />
          <span className="auth-salute-text">Виво-Эпсилон!</span>
          <span className="auth-salute-line" />
        </div>

        <p
          aria-hidden="true"
          style={{
            textAlign: 'center',
            fontSize: '0.62rem',
            letterSpacing: '0.08em',
            color: 'rgba(255,255,255,0.28)',
            margin: '0.55rem 0 0',
          }}
        >
          build {BUILD_TAG}
        </p>
      </div>
    </div>
  )
}