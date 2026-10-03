import { useEffect, useRef, useState } from 'react'
import { checkGroupKey, enterGroupKey, rememberGroupEntry } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { isGroupPreviewKey } from '../lib/groupPreviewKey'
import EntryFrame from '../components/EntryFrame'
import KeyField from '../components/KeyField'

export default function GroupKeyPage({ onBack, onPassed, onPreview, again = '' }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [key, setKey] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified] = useState(false)
  const [shake, setShake] = useState(0)
  const [needCode, setNeedCode] = useState(false)
  const [setup, setSetup] = useState(null)
  const [totp, setTotp] = useState('')
  const [copied, setCopied] = useState(false)
  const lastVerified = useRef('')

  useEffect(() => {
    const next = key.trim()
    if (next.length < 8) {
      setVerified(false)
      setVerifying(false)
      setNeedCode(false)
      setSetup(null)
      setTotp('')
      return undefined
    }
    if (next === lastVerified.current) {
      setVerified(true)
      return undefined
    }
    setVerified(false)
    if (isGroupPreviewKey(next)) {
      lastVerified.current = next
      setVerified(true)
      setError('')
      return undefined
    }

    let active = true
    const timer = window.setTimeout(async () => {
      setVerifying(true)
      setError('')
      try {
        const data = await checkGroupKey(next)
        if (!active) return
        lastVerified.current = next
        setNeedCode(Boolean(data?.needCode))
        setSetup(data?.setup || null)
        setTotp('')
        setVerified(true)
      } catch (err) {
        if (!active) return
        setVerified(false)
        lastVerified.current = ''
        if (err?.status === 403) {
          setError(err.message || 'Ключ не подошёл')
          setShake((n) => n + 1)
        } else {
          setError(err.message || 'Сервер не ответил. Кнопка откроется, когда ключ сойдётся.')
        }
      } finally {
        if (active) setVerifying(false)
      }
    }, 700)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [key])

  const submit = async (event) => {
    event.preventDefault()
    if (!verified || busy) return
    if (isGroupPreviewKey(key)) {
      onPreview?.()
      return
    }
    setBusy(true)
    setError('')
    try {
      const data = needCode
        ? await enterGroupKey(key.trim(), totp)
        : await checkGroupKey(key.trim(), { finish: true })
      if (!needCode && data?.needCode) {
        setNeedCode(true)
        setSetup(data.setup || null)
        setTotp('')
        return
      }
      if (data?.entryPass) rememberGroupEntry(data.entryPass)
      onPassed()
    } catch (err) {
      setVerified(false)
      lastVerified.current = ''
      setError(err.message || 'Ключ не подошёл')
      setShake((n) => n + 1)
    } finally {
      setBusy(false)
    }
  }

  return (
    <EntryFrame
      title="Панель администратора"
      lead={again ? 'Прошлый вход не подошёл. Напишите ключ ещё раз.' : 'Напишите ключ. Поле кода откроется само, когда ключ подойдёт.'}
      personal={personal}
      onBack={onBack}
    >
      <form className="auth-form auth-step" onSubmit={submit}>
        <KeyField
          label="Ключ кабинета"
          name="groupKey"
          value={key}
          onChange={(next) => {
            setKey(next)
            setError('')
          }}
          disabled={busy}
          invalid={shake}
        />

        {!verified && verifying && (
          <p className="auth-checking">
            <span className="auth-spinner" aria-hidden="true" />
            Проверяем ключ…
          </p>
        )}

        {!verified && !verifying && error && (
          <p className="auth-message auth-message-error" role="alert">{error}</p>
        )}

        <div className={`auth-reveal-slot${verified ? ' is-open' : ''}`} aria-hidden={verified ? undefined : true}>
          <div className="auth-reveal-inner">
            {needCode && setup && (
              <>
                <p className="auth-form-lead">Первый вход. Добавьте ключ в приложение с кодами и введите шесть цифр.</p>
                <div className="auth-qr-wrap">
                  <img className="auth-qr" src={setup.qrDataUrl} alt="QR для приложения с кодами" />
                </div>
                {setup.totpSecret && (
                  <button
                    type="button"
                    className="choice-close"
                    onClick={() => {
                      navigator.clipboard?.writeText(setup.totpSecret).catch(() => {})
                      setCopied(true)
                      window.setTimeout(() => setCopied(false), 1600)
                    }}
                  >
                    {copied ? 'Ключ скопирован' : 'Скопировать ключ'}
                  </button>
                )}
              </>
            )}
            {needCode && (
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
                    setError('')
                  }}
                  disabled={busy}
                />
              </label>
            )}
            <button
              type="submit"
              className={`auth-btn auth-btn-primary${busy ? ' is-working' : ''}`}
              disabled={!verified || busy || (needCode && totp.length !== 6)}
              tabIndex={verified ? 0 : -1}
            >
              {busy ? 'Входим…' : 'Войти'}
            </button>
          </div>
        </div>
      </form>
    </EntryFrame>
  )
}
