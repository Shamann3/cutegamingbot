import { useCallback, useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { AUTH_FIXES, AUTH_STEPS, AUTH_STORES, WORDS } from '../entry_design'

function stepSrc(file) {
  const base = import.meta.env.BASE_URL || '/'
  return `${base}${encodeURI(file)}`
}

function motionOff() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
}

export function preloadAuthShots() {
  if (typeof window === 'undefined') return
  for (const step of AUTH_STEPS) {
    const img = new Image()
    img.src = stepSrc(step.file)
  }
}

function focusNamed(kind) {
  const names = kind === 'totp'
    ? ['totp']
    : ['groupKey', 'inviteKey', 'loginKey']
  const input = names.map((name) => document.querySelector(`input[name="${name}"]`)).find(Boolean)
  if (!input) return false
  input.focus({ preventScroll: true })
  input.scrollIntoView({ block: 'center', behavior: motionOff() ? 'auto' : 'smooth' })
  return true
}

function focusCode() {
  focusNamed('totp')
}

function openStore(href) {
  const telegram = window.Telegram?.WebApp
  if (typeof telegram?.openLink === 'function') {
    telegram.openLink(href)
    return
  }
  window.open(href, '_blank', 'noopener,noreferrer')
}

function fixesFor(error) {
  const text = String(error || '')
  if (!text.trim()) return []
  return AUTH_FIXES.filter((fix) => fix.match && new RegExp(fix.match, 'i').test(text))
}

function WalkZoom({ src, title, onClose }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== 'Escape') return
      event.stopImmediatePropagation()
      onClose()
    }
    document.addEventListener('keydown', onKey, true)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = previous
    }
  }, [onClose])

  return createPortal(
    <div className="auth-walk-zoom" onClick={onClose}>
      <button type="button" className="auth-walk-zoom-close" onClick={onClose}>
        {WORDS.walkClose}
      </button>
      <img src={src} alt={title} decoding="async" onClick={(event) => event.stopPropagation()} />
    </div>,
    document.body,
  )
}

function StoreLinks() {
  return (
    <div className="auth-store">
      {AUTH_STORES.map((store) => (
        <a
          key={store.id}
          className="auth-store-link"
          href={store.href}
          onClick={(event) => {
            event.preventDefault()
            openStore(store.href)
          }}
        >
          {store.label}
        </a>
      ))}
    </div>
  )
}

function CodeClock() {
  const [left, setLeft] = useState(() => 30 - (Math.floor(Date.now() / 1000) % 30))
  useEffect(() => {
    const timer = window.setInterval(() => {
      setLeft(30 - (Math.floor(Date.now() / 1000) % 30))
    }, 250)
    return () => window.clearInterval(timer)
  }, [])
  return <p className="auth-clock">Новые цифры через {left} с. Впишите их сразу после смены.</p>
}

function FixBody({ fix, onShow }) {
  const [copyState, setCopyState] = useState('')
  const stepIndex = AUTH_STEPS.findIndex((step) => step.id === fix.step)

  const copySecret = async () => {
    const value = document.querySelector('[data-setup-secret]')?.getAttribute('data-setup-secret') || ''
    if (!value) {
      setCopyState('missing')
      return
    }
    try {
      await navigator.clipboard.writeText(value)
      setCopyState('ok')
    } catch {
      setCopyState(value)
    }
  }

  return (
    <div className="auth-fix-body">
      <p>{fix.do}</p>
      {fix.stores && <StoreLinks />}
      {fix.clock && <CodeClock />}
      {fix.copy && (
        <button type="button" className="auth-walk-next auth-walk-next-inline" onClick={copySecret}>
          {WORDS.copyKey}
        </button>
      )}
      {copyState === 'ok' && <p className="auth-fix-note">{WORDS.walkCopied}</p>}
      {copyState === 'missing' && <p className="auth-fix-note">{WORDS.walkNoSecret}</p>}
      {copyState && copyState !== 'ok' && copyState !== 'missing' && (
        <code className="auth-fix-secret">{copyState}</code>
      )}
      {fix.focus && (
        <button type="button" className="auth-walk-next auth-walk-next-inline" onClick={() => focusNamed(fix.focus)}>
          {fix.focus === 'totp' ? WORDS.walkDone : WORDS.groupKey}
        </button>
      )}
      {stepIndex >= 0 && (
        <button type="button" className="auth-walk-missing" onClick={() => onShow(stepIndex)}>
          {WORDS.walkShow}
        </button>
      )}
    </div>
  )
}

function FixList({ fixes, onShow }) {
  const [openId, setOpenId] = useState(fixes.length === 1 ? fixes[0].id : '')
  return (
    <ul className="auth-fixes">
      {fixes.map((fix) => {
        const opened = openId === fix.id
        return (
          <li key={fix.id}>
            <button
              type="button"
              className="auth-fix-ask"
              aria-expanded={opened}
              onClick={() => setOpenId(opened ? '' : fix.id)}
            >
              {fix.ask}
            </button>
            {opened && <FixBody fix={fix} onShow={onShow} />}
          </li>
        )
      })}
    </ul>
  )
}

/** Картинки Google Authenticator: сразу кадр, одна строка, куда нажать. */
export default function AuthWalk({ onDone, returning = false }) {
  const [stuck, setStuck] = useState(false)
  const [showShots, setShowShots] = useState(!returning)
  const [zoom, setZoom] = useState(-1)
  const zoomStep = zoom >= 0 ? AUTH_STEPS[zoom] : null

  useEffect(() => {
    preloadAuthShots()
  }, [])

  const finish = () => {
    focusCode()
    onDone?.()
  }

  return (
    <section className="auth-shots" aria-label={WORDS.walkTitle}>
      {returning && (
        <>
          <p className="auth-shot-have">{WORDS.walkHave}</p>
          <button type="button" className="auth-walk-next auth-walk-next-inline" onClick={finish}>
            {WORDS.walkDone}
          </button>
          <button
            type="button"
            className="auth-walk-missing"
            aria-expanded={showShots}
            onClick={() => setShowShots((open) => !open)}
          >
            {WORDS.walkMissing}
          </button>
        </>
      )}

      {showShots && (
        <ol className="auth-shot-list">
          {AUTH_STEPS.map((step, index) => (
            <li key={step.id} className="auth-shot">
              <button
                type="button"
                className="auth-shot-frame"
                aria-label={`${WORDS.walkTap}: ${step.title}`}
                onClick={() => setZoom(index)}
              >
                <img
                  src={stepSrc(step.file)}
                  alt=""
                  decoding="async"
                  fetchPriority={index === 0 ? 'high' : 'low'}
                  draggable={false}
                />
              </button>
              <p className="auth-shot-line">
                <span className="auth-shot-num" aria-hidden="true">{index + 1}</span>
                {step.line}
              </p>
              {step.id === 'store' && <StoreLinks />}
            </li>
          ))}
        </ol>
      )}

      {showShots && (
        <button type="button" className="auth-walk-next" onClick={finish}>
          {WORDS.walkDone}
        </button>
      )}

      <button
        type="button"
        className="auth-walk-missing"
        aria-expanded={stuck}
        onClick={() => setStuck((open) => !open)}
      >
        {WORDS.walkStuck}
      </button>
      {stuck && <FixList fixes={AUTH_FIXES} onShow={setZoom} />}

      {zoomStep && (
        <WalkZoom src={stepSrc(zoomStep.file)} title={zoomStep.line} onClose={() => setZoom(-1)} />
      )}
    </section>
  )
}

/** Ошибка входа сама открывает тот вариант, который её снимает. */
export function AuthRescue({ error }) {
  const [zoom, setZoom] = useState(-1)
  const fixes = fixesFor(error)
  const zoomStep = zoom >= 0 ? AUTH_STEPS[zoom] : null
  if (!fixes.length) return null
  return (
    <div className="auth-rescue" role="status">
      <FixList fixes={fixes} onShow={setZoom} />
      {zoomStep && (
        <WalkZoom src={stepSrc(zoomStep.file)} title={zoomStep.line} onClose={() => setZoom(-1)} />
      )}
    </div>
  )
}

/** Обычный вход: шесть цифр уже в приложении. Картинки — если строки нет. */
export function AuthWalkHelp() {
  const titleId = useId()
  const [open, setOpen] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const close = useCallback(() => {
    setLeaving(true)
    window.setTimeout(() => {
      setOpen(false)
      setLeaving(false)
    }, motionOff() ? 0 : 220)
  }, [])

  useEffect(() => {
    if (!open || leaving) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, leaving, close])

  return (
    <>
      <button type="button" className="auth-walk-help" onClick={() => setOpen(true)}>
        {WORDS.walkLost}
      </button>
      {open && createPortal(
        <div className={`choice-layer entry-guide-layer auth-walk-layer${leaving ? ' is-leaving' : ''}`} onClick={close}>
          <div className="choice-dim" />
          <div className="choice-sheet-motion">
            <div
              className="choice-sheet entry-guide-sheet auth-walk-sheet is-visual"
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              onClick={(event) => event.stopPropagation()}
            >
              <p id={titleId} className="choice-sheet-title">{WORDS.walkLost}</p>
              <div className="entry-guide-body">
                <AuthWalk returning onDone={close} />
              </div>
              <button type="button" className="choice-close" onClick={close}>{WORDS.close}</button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
