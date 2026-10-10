import { useEffect, useRef, useState } from 'react'
import { checkGroupKey, enterGroupKey, fetchAdminAuthStatus, rememberGroupEntry } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { isGroupPreviewKey } from '../lib/groupPreviewKey'
import { portraitFrom, rememberPortrait } from '../lib/gateRecovery'
import EntryFrame from '../components/EntryFrame'
import { AuthRescue, EntryHelp } from '../components/AuthWalk'
import EntryGuide from '../components/EntryGuide'
import KeyField from '../components/KeyField'
import { SCREENS, WORDS } from '../entry_design'

export default function GroupKeyPage({ onBack, onPassed, onApply, onPreview, again = '' }) {
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
  const [gate, setGate] = useState('check')

  useEffect(() => {
    let alive = true
    fetchAdminAuthStatus()
      .then((status) => {
        if (!alive) return
        const face = portraitFrom(status)
        rememberPortrait(face)
        if (face.isProjectCreator) {
          setGate('creator')
          onPassed()
          return
        }
        if (!face.groupCanEnter) {
          setGate('apply')
          onApply?.()
          return
        }
        setGate('key')
      })
      .catch(() => {
        if (alive) setGate('key')
      })
    return () => { alive = false }
  }, [onPassed, onApply])

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
        if (err?.code === 'need_apply') {
          onApply?.()
          return
        }
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
      if (err?.code === 'need_apply') {
        onApply?.()
        return
      }
      const message = err.message || 'Ключ не подошёл'
      if (!/код не подош/i.test(message)) {
        setVerified(false)
        lastVerified.current = ''
      }
      setError(message)
      setShake((n) => n + 1)
    } finally {
      setBusy(false)
    }
  }

  if (gate !== 'key') {
    return (
      <EntryFrame
        title={WORDS.groupTitle}
        lead={gate === 'creator' ? 'Кабинет открывается сразу.' : 'Сверяем, открыт ли вам кабинет.'}
        personal={personal}
        onBack={onBack}
      >
        <p className="auth-checking">
          <span className="auth-spinner" aria-hidden="true" />
          {gate === 'creator' ? 'Открываем кабинет…' : 'Проверяем вход…'}
        </p>
      </EntryFrame>
    )
  }

  return (
    <EntryFrame
      title={WORDS.groupTitle}
      lead={again ? WORDS.groupAgain : WORDS.groupLead}
      personal={personal}
      onBack={onBack}
    >
      <form className="auth-form auth-step" onSubmit={submit}>
        <EntryGuide screen={SCREENS.groupKey} at={!verified ? 'key' : needCode && setup && !totp ? 'app' : 'code'} />
        <EntryHelp setup={setup} />

        <KeyField
          label={WORDS.groupKey}
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
            {WORDS.checking}
          </p>
        )}

        {!verified && !verifying && error && (
          <>
            <p className="auth-message auth-message-error" role="alert">{error}</p>
            <AuthRescue error={error} />
          </>
        )}

        <div className={`auth-reveal-slot${verified ? ' is-open' : ''}`} aria-hidden={verified ? undefined : true}>
          <div className="auth-reveal-inner">
            {needCode && setup && (
              <>
                <p className="auth-form-lead">{WORDS.groupFirst}</p>
                <div className="auth-qr-wrap">
                  <img className="auth-qr" src={setup.qrDataUrl} alt={WORDS.qrAlt} />
                </div>
                {setup.totpSecret && (
                  <button
                    type="button"
                    className="choice-close"
                    data-setup-secret={setup.totpSecret}
                    onClick={() => {
                      navigator.clipboard?.writeText(setup.totpSecret).catch(() => {})
                      setCopied(true)
                      window.setTimeout(() => setCopied(false), 1600)
                    }}
                  >
                    {copied ? WORDS.copied : WORDS.copyKey}
                  </button>
                )}
              </>
            )}
            {error && verified && (
              <>
                <p className="auth-message auth-message-error" role="alert">{error}</p>
                <AuthRescue error={error} />
              </>
            )}
            {needCode && (
              <label className="auth-field">
                <span className="auth-label">{WORDS.code}</span>
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
              {busy ? WORDS.entering : WORDS.enter}
            </button>
          </div>
        </div>
      </form>
    </EntryFrame>
  )
}
