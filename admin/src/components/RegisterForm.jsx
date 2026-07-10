import { useEffect, useRef, useState } from 'react'
import { revealRegisterCode } from '../lib/adminClient'
import KeyField from './KeyField'

export default function RegisterForm({
  onStart,
  onConfirm,
  onEditKey,
  loading,
  error,
  info,
  setup,
  registered,
}) {
  const [inviteKey, setInviteKey] = useState('')
  const [totp, setTotp] = useState('')
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')
  const lastTried = useRef('')

  useEffect(() => {
    setTotp('')
    setLocalError('')
  }, [setup?.setupToken])

  const tryStart = (raw) => {
    const key = (raw ?? inviteKey).trim()
    if (!key || setup || loading) return
    if (key === lastTried.current) return
    lastTried.current = key
    onStart(key)
  }

  // Автопроверка ключа: после короткой паузы в наборе сам валидируем ключ.
  useEffect(() => {
    const key = inviteKey.trim()
    if (!key || setup || loading || key === lastTried.current) return
    const timer = setTimeout(() => tryStart(key), 700)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inviteKey, setup, loading])

  const handleKeyChange = (next) => {
    setInviteKey(next)
    setLocalError('')
    if (onEditKey) onEditKey()
  }

  const copyKey = () => {
    navigator.clipboard?.writeText(setup?.totpSecret || '').catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  const runConfirm = async () => {
    if (busy || loading || totp.length !== 6 || !setup?.setupToken) return
    setBusy(true)
    setLocalError('')
    try {
      const data = await revealRegisterCode(setup.setupToken, totp)
      const code = data?.code
      if (!code) {
        setLocalError('Не удалось подтвердить код. Попробуйте снова.')
        return
      }
      await onConfirm(code)
    } catch (err) {
      setLocalError(err.message || 'Не удалось завершить. Попробуйте снова.')
    } finally {
      setBusy(false)
    }
  }

  const handleFormSubmit = (event) => {
    event.preventDefault()
    if (!setup) {
      tryStart()
      return
    }
    runConfirm()
  }

  if (registered) {
    return (
      <div className="auth-form auth-step">
        <p className="auth-message auth-message-info">
          Аккаунт уже зарегистрирован. Перейдите во вкладку «Вход».
        </p>
      </div>
    )
  }

  const shownError = localError || error
  const working = busy || loading

  return (
    <form className="auth-form auth-step" onSubmit={handleFormSubmit}>
      <p className="auth-form-lead">
        {setup
          ? 'Отсканируйте QR или введите ключ в аутентификатор, затем введите код.'
          : 'Введите ключ доступа — проверка начнётся автоматически.'}
      </p>

      <KeyField
        label="Ключ доступа"
        name="inviteKey"
        value={inviteKey}
        onChange={handleKeyChange}
        disabled={loading || Boolean(setup)}
      />

      {!setup && loading && (
        <p className="auth-checking">
          <span className="auth-spinner" aria-hidden="true" />
          Проверяем ключ…
        </p>
      )}

      {!setup && !loading && info && (
        <p className="auth-message auth-message-info">{info}</p>
      )}
      {!setup && !loading && error && (
        <p className="auth-message auth-message-error">{error}</p>
      )}

      <div className={`auth-reveal-slot${setup ? ' is-open' : ''}`}>
        <div className="auth-reveal-inner">
          {setup && (
            <>
              <div className="auth-qr-wrap">
                <img className="auth-qr" src={setup.qrDataUrl} alt="QR для аутентификатора" />
                {setup.authenticatorLabel && (
                  <p className="auth-qr-caption">{setup.authenticatorLabel}</p>
                )}
              </div>

              {setup.totpSecret && (
                <div className="auth-totp-key-block">
                  <p className="auth-totp-key-label">Ключ вручную</p>
                  <div className="auth-totp-key-row">
                    <code className="auth-totp-key">{setup.totpSecret}</code>
                    <button type="button" className="auth-totp-copy-btn" onClick={copyKey}>
                      {copied ? '✓' : '📋'}
                    </button>
                  </div>
                </div>
              )}

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
              {shownError && <p className="auth-message auth-message-error">{shownError}</p>}

              <button
                type="submit"
                className={`auth-btn auth-btn-primary${working ? ' is-working' : ''}`}
                disabled={working || totp.length !== 6}
              >
                {working ? 'Завершаем…' : 'Завершить регистрацию'}
              </button>
            </>
          )}
        </div>
      </div>
    </form>
  )
}
