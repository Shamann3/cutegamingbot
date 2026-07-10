import { useEffect, useRef, useState } from 'react'
import { hasTelegramInitData, revealLoginCode, verifyLoginKey } from '../lib/adminClient'
import KeyField from './KeyField'

const CAN_AUTH_DEV = import.meta.env.DEV && import.meta.env.VITE_DEV_USER_ID

export default function LoginForm({ onSubmit, loading, error, info }) {
  const [loginKey, setLoginKey] = useState('')
  const [totp, setTotp] = useState('')
  const [busy, setBusy] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified] = useState(false)
  const [localError, setLocalError] = useState('')
  const lastVerified = useRef('')

  // Автопроверка ключа входа: код появляется только при верном ключе.
  useEffect(() => {
    const key = loginKey.trim()
    if (!key) {
      setVerified(false)
      return
    }
    if (key === lastVerified.current) {
      setVerified(true)
      return
    }
    setVerified(false)

    if (!hasTelegramInitData() && !CAN_AUTH_DEV) {
      setLocalError('Откройте панель через admin-бота в Telegram.')
      return
    }

    let active = true
    const timer = setTimeout(async () => {
      setVerifying(true)
      setLocalError('')
      try {
        await verifyLoginKey(key)
        if (active) {
          lastVerified.current = key
          setVerified(true)
        }
      } catch (err) {
        if (!active) return
        // 403 — определённо неверный ключ / неактивный аккаунт: не открываем код.
        if (err?.status === 403) {
          setVerified(false)
          setLocalError(err.message || 'Неверный ключ входа.')
        } else {
          // Эндпоинт недоступен (404), сеть/сервер — не блокируем:
          // даём ввести код, финальный вход всё равно проверит ключ.
          lastVerified.current = key
          setVerified(true)
        }
      } finally {
        if (active) setVerifying(false)
      }
    }, 700)

    return () => {
      active = false
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loginKey])

  const working = busy || loading
  const shownError = localError || error

  const handleKeyChange = (next) => {
    setLoginKey(next)
    setLocalError('')
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (working || !verified || totp.length !== 6) return
    setBusy(true)
    setLocalError('')
    try {
      const data = await revealLoginCode(loginKey.trim(), totp)
      const code = data?.code
      if (!code) {
        setLocalError('Не удалось подтвердить код. Попробуйте снова.')
        return
      }
      await onSubmit({ loginKey: loginKey.trim(), totp: code })
    } catch (err) {
      setLocalError(err.message || 'Не удалось войти. Попробуйте снова.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="auth-form auth-step" onSubmit={handleSubmit}>
      <p className="auth-form-lead">Введите ключ входа.</p>

      <KeyField
        label="Ключ входа"
        name="loginKey"
        value={loginKey}
        onChange={handleKeyChange}
        disabled={busy}
      />

      {!verified && verifying && (
        <p className="auth-checking">
          <span className="auth-spinner" aria-hidden="true" />
          Проверяем ключ…
        </p>
      )}

      {!verified && !verifying && shownError && (
        <p className="auth-message auth-message-error">{shownError}</p>
      )}

      <div className={`auth-reveal-slot${verified ? ' is-open' : ''}`}>
        <div className="auth-reveal-inner">
          <label className="auth-field">
            <span className="auth-label">Код из приложения</span>
            <input
              className="auth-input auth-input-code"
              name="totp"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              maxLength={6}
              value={totp}
              onChange={(event) => {
                setTotp(event.target.value.replace(/\D/g, '').slice(0, 6))
                setLocalError('')
              }}
              disabled={working}
            />
          </label>

          {info && <p className="auth-message auth-message-info">{info}</p>}
          {verified && shownError && (
            <p className="auth-message auth-message-error">{shownError}</p>
          )}

          <button
            type="submit"
            className={`auth-btn auth-btn-primary${working ? ' is-working' : ''}`}
            disabled={working || totp.length !== 6}
          >
            {working ? 'Входим…' : 'Войти'}
          </button>
        </div>
      </div>
    </form>
  )
}
