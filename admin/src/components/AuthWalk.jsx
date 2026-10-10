import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AUTH_STEPS, WORDS } from '../entry_design'

function stepSrc(file) {
  const base = import.meta.env.BASE_URL || '/'
  return `${base}${encodeURI(file)}`
}

function motionOff() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
}

function focusCode(node) {
  const input = node?.closest?.('form')?.querySelector('input[name="totp"]')
    || document.querySelector('input[name="totp"]')
  if (!input) return
  input.focus({ preventScroll: true })
  input.scrollIntoView({ block: 'nearest', behavior: motionOff() ? 'auto' : 'smooth' })
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

/** Четыре раздела Google Authenticator. Тексты и файлы — AUTH_STEPS в entry_design.js. */
export default function AuthWalk({ onDone, returning = false }) {
  const [index, setIndex] = useState(0)
  const [showSteps, setShowSteps] = useState(!returning)
  const [zoom, setZoom] = useState(-1)
  const rootRef = useRef(null)
  const heads = useRef([])
  const moved = useRef(false)

  const finish = () => {
    focusCode(rootRef.current)
    onDone?.()
  }

  const open = (next) => {
    const clamped = Math.max(0, Math.min(AUTH_STEPS.length - 1, next))
    setShowSteps(true)
    setIndex(clamped)
  }

  useEffect(() => {
    if (!moved.current) {
      moved.current = true
      return undefined
    }
    heads.current[index]?.scrollIntoView({ block: 'nearest', behavior: motionOff() ? 'auto' : 'smooth' })
    return undefined
  }, [index])

  const zoomStep = zoom >= 0 ? AUTH_STEPS[zoom] : null

  return (
    <section ref={rootRef} className="auth-walk" aria-label={WORDS.walkTitle}>
      {returning && (
        <>
          <p className="auth-walk-fork">{WORDS.walkHave}</p>
          <button type="button" className="auth-walk-next auth-walk-next-inline" onClick={finish}>
            {WORDS.walkDone}
          </button>
          <button
            type="button"
            className="auth-walk-missing"
            aria-expanded={showSteps}
            onClick={() => setShowSteps((openSteps) => !openSteps)}
          >
            {WORDS.walkMissing}
          </button>
        </>
      )}

      {showSteps && (
        <>
          <p className="auth-walk-fork">{WORDS.walkLead}</p>
          {!returning && <p className="auth-walk-qr">{WORDS.walkQr}</p>}
          <ol className="auth-walk-sections">
            {AUTH_STEPS.map((step, dot) => {
              const opened = dot === index
              return (
                <li key={step.id} className={`auth-walk-section${opened ? ' is-open' : ''}${dot < index ? ' is-done' : ''}`}>
                  <button
                    ref={(node) => { heads.current[dot] = node }}
                    type="button"
                    className="auth-walk-head"
                    aria-expanded={opened}
                    onClick={() => open(dot)}
                  >
                    <span className="auth-walk-num" aria-hidden="true">{dot < index ? '✓' : dot + 1}</span>
                    <span className="auth-walk-name">{step.title}</span>
                  </button>
                  {opened && (
                    <div className="auth-walk-panel">
                      <p className="auth-walk-line">{step.line}</p>
                      <button
                        type="button"
                        className="auth-walk-frame"
                        aria-label={`${WORDS.walkTap} ${step.title}`}
                        onClick={() => setZoom(dot)}
                      >
                        <img src={stepSrc(step.file)} alt="" decoding="async" draggable={false} />
                      </button>
                      <p className="auth-walk-tap">{WORDS.walkTap}</p>
                      <button
                        type="button"
                        className="auth-walk-next"
                        onClick={() => (dot === AUTH_STEPS.length - 1 ? finish() : open(dot + 1))}
                      >
                        {dot === AUTH_STEPS.length - 1 ? WORDS.walkDone : WORDS.walkNext}
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
        </>
      )}

      {zoomStep && (
        <WalkZoom src={stepSrc(zoomStep.file)} title={zoomStep.line} onClose={() => setZoom(-1)} />
      )}
    </section>
  )
}

/** Обычный вход: сначала где лежат шесть цифр. Картинки — только если строки в приложении нет. */
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
              className="choice-sheet entry-guide-sheet auth-walk-sheet"
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              onClick={(event) => event.stopPropagation()}
            >
              <p id={titleId} className="choice-sheet-title">{WORDS.walkLost}</p>
              <AuthWalk returning onDone={close} />
              <button type="button" className="choice-close" onClick={close}>{WORDS.close}</button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
