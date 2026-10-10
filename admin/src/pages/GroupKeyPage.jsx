import { useEffect, useRef, useState } from 'react'
import { checkGroupKey, enterGroupKey, fetchAdminAuthStatus, rememberGroupEntry } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { isGroupPreviewKey } from '../lib/groupPreviewKey'
import { portraitFrom, rememberPortrait } from '../lib/gateRecovery'
import EntryFrame from '../components/EntryFrame'
import { AppKeyCard, AuthRescue, CodeField } from '../components/AuthWalk'
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
      setNeedCode(true)
      setSetup({
        qrDataUrl: 'data:image/svg+xml,' + encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#fff"/><path fill="#111" d="M4 4h20v20H4zm4 4v12h12V8zm28-4h20v20H36zm4 4v12h12V8zM4 36h20v20H4zm4 4v12h12V40zm8-28h4v4h-4zm28 0h4v4h-4zM36 36h8v4h-8zm12 0h8v8h-4v-4h-4zm-8 8h4v8h-4zm8 4h8v8h-8zM28 4h4v8h-4zm0 12h4v8h-8v-4h4zm8 8h8v4h-8zM4 28h8v4H4zm16 0h12v4H20zm16 0h8v4h-8zm16 0h4v8h-4z"/></svg>',
        ),
        totpSecret: 'JBSWY3DPEHPK3PXP',
      })
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
      onPassed(needCode ? totp : undefined)
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
            {needCode && setup && <AppKeyCard setup={setup} />}
            {error && verified && (
              <>
                <p className="auth-message auth-message-error" role="alert">{error}</p>
                <AuthRescue error={error} />
              </>
            )}
            {needCode && (
              <CodeField
                value={totp}
                disabled={busy}
                onChange={(event) => {
                  setTotp(event.target.value.replace(/\D/g, '').slice(0, 6))
                  setError('')
                }}
              />
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
