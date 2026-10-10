import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AUTH_FIXES, AUTH_STEPS, AUTH_STORES, KEY_AFTER, WORDS } from '../entry_design'

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

export function AppKeyCard({ setup }) {
  if (!setup?.qrDataUrl && !setup?.totpSecret) return null
  return (
    <section className="app-key-card" aria-label={WORDS.appKeyTitle}>
      <p className="app-key-title">{WORDS.appKeyTitle}</p>
      <p className="app-key-lead">{WORDS.appKeyLead}</p>
      {setup.authenticatorLabel && <p className="app-key-name">{setup.authenticatorLabel}</p>}
      {setup.qrDataUrl && (
        <figure className="auth-help-qr app-key-qr">
          <img src={setup.qrDataUrl} alt={WORDS.qrAlt} />
          <figcaption>{WORDS.walkQrShot}</figcaption>
        </figure>
      )}
      <CopyKey secret={setup.totpSecret || ''} expectQr />
    </section>
  )
}

const VEIL_GLYPHS = '█▓▒░#@$%&*+/='
const VEILS = ['scan', 'rain', 'shutter']
const SAMPLE_CODES = ['482193', '705614', '193850']

function useVeilCycle(active) {
  const nodeRef = useRef(null)
  const [veil, setVeil] = useState(() => VEILS[Math.floor(Math.random() * VEILS.length)])

  useEffect(() => {
    if (!active || motionOff()) return undefined
    const node = nodeRef.current
    let timer = 0
    let seen = true
    const wait = document.body.classList.contains('perf-light') ? 7200 : 4200
    const stop = () => window.clearInterval(timer)
    const arm = () => {
      stop()
      if (!seen || document.hidden) return
      timer = window.setInterval(() => {
        setVeil((current) => VEILS[(VEILS.indexOf(current) + 1) % VEILS.length])
      }, wait)
    }
    let observer
    if (node && typeof IntersectionObserver === 'function') {
      observer = new IntersectionObserver(([entry]) => {
        seen = Boolean(entry?.isIntersecting)
        if (seen) arm()
        else stop()
      })
      observer.observe(node)
    }
    const onVis = () => {
      if (document.hidden) stop()
      else if (seen) arm()
    }
    document.addEventListener('visibilitychange', onVis)
    arm()
    return () => {
      stop()
      observer?.disconnect()
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [active])

  return [veil, nodeRef]
}

function veilText(secret) {
  const count = Math.max(8, String(secret || '').length)
  let text = ''
  for (let index = 0; index < count; index += 1) text += VEIL_GLYPHS[index % VEIL_GLYPHS.length]
  return text
}

function StageRail({ count, index, onPick, label }) {
  return (
    <div className="auth-stage-rail" role="tablist" aria-label={label}>
      {Array.from({ length: count }, (_, dot) => (
        <button
          key={dot}
          type="button"
          className={`auth-stage-dot${dot === index ? ' is-on' : ''}${dot < index ? ' is-done' : ''}`}
          aria-label={`${dot + 1} из ${count}`}
          aria-current={dot === index ? 'step' : undefined}
          onClick={() => onPick(dot)}
        />
      ))}
    </div>
  )
}

function StageNav({ index, last, onPrev, onNext, doneLabel }) {
  return (
    <div className="auth-stage-nav">
      <button type="button" className="auth-stage-back" disabled={index === 0} onClick={onPrev}>
        {WORDS.walkBack}
      </button>
      <button type="button" className="auth-stage-next" onClick={onNext}>
        {last ? doneLabel : WORDS.walkNext}
      </button>
    </div>
  )
}

function useStage(count) {
  const [index, setIndex] = useState(0)
  const [dir, setDir] = useState(1)
  const [turned, setTurned] = useState(false)
  const go = (next) => {
    const clamped = Math.max(0, Math.min(count - 1, next))
    if (clamped === index) return clamped
    setDir(clamped > index ? 1 : -1)
    setTurned(true)
    setIndex(clamped)
    return clamped
  }
  return { index, dir, turned, go }
}

function KeyAfter({ onDone }) {
  const [zoom, setZoom] = useState(-1)
  const stage = useStage(KEY_AFTER.length)
  const step = KEY_AFTER[stage.index]
  const shot = step.step ? AUTH_STEPS.find((item) => item.id === step.step) : null
  const zoomStep = zoom >= 0 ? AUTH_STEPS[zoom] : null
  const last = stage.index === KEY_AFTER.length - 1

  useEffect(() => {
    const nextId = KEY_AFTER[stage.index + 1]?.step
    const files = [
      shot?.file,
      nextId ? AUTH_STEPS.find((item) => item.id === nextId)?.file : '',
    ].filter(Boolean)
    for (const file of files) {
      const img = new Image()
      img.src = stepSrc(file)
    }
  }, [shot, stage.index])

  return (
    <div className="auth-stage">
      <StageRail count={KEY_AFTER.length} index={stage.index} onPick={stage.go} label={WORDS.appKeyNext} />
      <div
        key={step.id}
        className={`auth-stage-view${stage.turned ? ' is-turn' : ''}`}
        style={{ '--stage-x': stage.dir > 0 ? '14px' : '-14px' }}
      >
        <p className="auth-after-title">
          <span className="auth-shot-num" aria-hidden="true">{stage.index + 1}</span>
          {step.title}
        </p>
        <p className="auth-after-line">{step.line}</p>
        {shot && (
          <button
            type="button"
            className={`auth-path-frame auth-after-shot${shot.id === 'plus' ? ' is-mark' : ''}`}
            aria-label={`${WORDS.walkTap}: ${shot.title}`}
            onClick={() => setZoom(AUTH_STEPS.indexOf(shot))}
          >
            <img src={stepSrc(shot.file)} alt="" decoding="async" draggable={false} />
          </button>
        )}
        {step.stores && <StoreLinks />}
      </div>
      <StageNav
        index={stage.index}
        last={last}
        onPrev={() => stage.go(stage.index - 1)}
        onNext={() => (last ? onDone() : stage.go(stage.index + 1))}
        doneLabel={WORDS.walkDone}
      />
      {zoomStep && (
        <WalkZoom src={stepSrc(zoomStep.file)} title={zoomStep.title} onClose={() => setZoom(-1)} />
      )}
    </div>
  )
}

function DigitSample() {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    if (motionOff()) return undefined
    const wait = document.body.classList.contains('perf-light') ? 3200 : 1800
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % SAMPLE_CODES.length)
    }, wait)
    return () => window.clearInterval(timer)
  }, [])
  const digits = SAMPLE_CODES[index]
  return (
    <div className="auth-digit-card" aria-hidden="true">
      <span className="auth-digit-app">Google Authenticator</span>
      <span className="auth-digit-row">
        <span className="auth-digit-name">Epsilon</span>
        <span key={digits} className="auth-digit-code">{`${digits.slice(0, 3)} ${digits.slice(3)}`}</span>
      </span>
      <span className="auth-digit-seek" />
      <span className="auth-digit-note">{WORDS.codeSample}</span>
    </div>
  )
}

function placeInCode(event, value) {
  const cells = event.currentTarget.parentElement?.querySelectorAll('.otp-cell') || []
  let index = String(value || '').length
  cells.forEach((cell, cellIndex) => {
    if (event.clientX >= cell.getBoundingClientRect().left) index = cellIndex
  })
  return Math.min(index, String(value || '').length)
}

export function CodeField({
  value,
  onChange,
  disabled = false,
  tabIndex,
  submitLabel = WORDS.enter,
}) {
  const [open, setOpen] = useState(false)
  const [spot, setSpot] = useState(false)
  const [focused, setFocused] = useState(false)
  const [caret, setCaret] = useState(0)
  const spotTimer = useRef(0)
  const inputRef = useRef(null)
  const stage = useStage(2)
  const digits = String(value || '').replace(/\D/g, '').slice(0, 6)

  useEffect(() => () => window.clearTimeout(spotTimer.current), [])

  const commit = (raw, nextCaret) => {
    const next = String(raw || '').replace(/\D/g, '').slice(0, 6)
    onChange({ target: { value: next } })
    const place = Math.min(nextCaret ?? next.length, next.length)
    setCaret(place)
    inputRef.current?.setSelectionRange(place, place)
  }

  const pulse = () => {
    setSpot(true)
    window.clearTimeout(spotTimer.current)
    spotTimer.current = window.setTimeout(() => setSpot(false), motionOff() ? 0 : 1600)
  }

  const show = () => {
    setOpen((was) => !was)
    setSpot(false)
    stage.go(0)
  }

  const go = (next) => {
    const landed = stage.go(next)
    if (landed === 1) pulse()
  }

  return (
    <div className={`auth-code-block${spot ? ' is-spot' : ''}${open ? ' is-open' : ''}`}>
      <label className="auth-field">
        <span className="auth-label">{WORDS.code}</span>
        <div className={`otp${focused ? ' is-focus' : ''}`}>
          <div className="otp-cells" aria-hidden="true">
            {Array.from({ length: 6 }, (_, index) => {
              const mark = digits[index] || ''
              const active = focused && (caret === index || (caret >= 6 && index === 5))
              return (
                <span
                  key={index}
                  className={`otp-cell${mark ? ' is-filled' : ''}${active ? ' is-on' : ''}${index === 2 ? ' is-gap' : ''}`}
                >
                  {mark ? <span key={mark} className="otp-digit">{mark}</span> : null}
                </span>
              )
            })}
          </div>
          <input
            ref={inputRef}
            className="otp-capture"
            name="totp"
            inputMode="numeric"
            autoComplete="one-time-code"
            autoCorrect="off"
            spellCheck="false"
            maxLength={6}
            tabIndex={tabIndex}
            value={digits}
            disabled={disabled}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onSelect={(event) => setCaret(event.target.selectionStart || 0)}
            onClick={(event) => {
              const place = placeInCode(event, digits)
              setCaret(place)
              event.currentTarget.setSelectionRange(place, place)
            }}
            onChange={(event) => commit(event.target.value, event.target.selectionStart)}
          />
        </div>
      </label>
      <button
        type="button"
        className="auth-side-ask auth-code-ask"
        aria-expanded={open}
        onClick={show}
      >
        {WORDS.codeFind}
      </button>
      {open && (
        <div className="auth-stage" role="region" aria-label={WORDS.codeFind}>
          <StageRail count={2} index={stage.index} onPick={go} label={WORDS.codeFind} />
          <div
            key={stage.index}
            className={`auth-stage-view${stage.turned ? ' is-turn' : ''}`}
            style={{ '--stage-x': stage.dir > 0 ? '14px' : '-14px' }}
          >
            {stage.index === 0 ? (
              <>
                <p className="auth-after-title">{WORDS.codeStage1}</p>
                <DigitSample />
                <p className="auth-where-lead">{WORDS.codeWhere}</p>
              </>
            ) : (
              <>
                <p className="auth-after-title">{WORDS.codeStage2}</p>
                <p className="auth-where-next">
                  {WORDS.codeThen} <b>{submitLabel}</b>.
                </p>
              </>
            )}
          </div>
          <StageNav
            index={stage.index}
            last={stage.index === 1}
            onPrev={() => go(stage.index - 1)}
            onNext={() => (stage.index === 1 ? focusCode() : go(1))}
            doneLabel={WORDS.walkDone}
          />
        </div>
      )}
    </div>
  )
}

export function CopyKey({ secret, expectQr = false, onNeedKey }) {
  const [copied, setCopied] = useState(false)
  const [held, setHeld] = useState(false)
  const [phase, setPhase] = useState('veiled')
  const [next, setNext] = useState(false)
  const revealTimer = useRef(0)
  const mask = veilText(secret)
  const open = phase === 'open'
  const shown = phase === 'veiled' ? mask : secret
  const [veil, veilRef] = useVeilCycle(Boolean(secret) && !open)

  useEffect(() => () => window.clearTimeout(revealTimer.current), [])

  const markCopied = (ok) => {
    if (ok) {
      setCopied(true)
      setHeld(false)
      window.setTimeout(() => setCopied(false), 1600)
      return
    }
    setHeld(true)
  }

  const writeSecret = async () => {
    try {
      await navigator.clipboard.writeText(secret)
      return true
    } catch {
      return false
    }
  }

  const reveal = () => {
    if (!secret || phase !== 'veiled') return
    if (motionOff()) {
      setPhase('open')
      return
    }
    setPhase('clear')
    revealTimer.current = window.setTimeout(() => setPhase('open'), 320)
  }

  const copy = async () => {
    if (!secret) {
      onNeedKey?.()
      return
    }
    markCopied(await writeSecret())
  }

  if (!secret && !expectQr) return null

  return (
    <div className="auth-setup" data-setup-secret={secret || undefined}>
      {secret && <p className="auth-key-kicker">{WORDS.appKeyHead}</p>}
      {secret && (
        <div className="auth-key-stage">
          {open ? (
            <button type="button" className="auth-setup-secret is-open" onClick={copy}>
              {secret}
            </button>
          ) : (
            <button
              type="button"
              ref={veilRef}
              className={`auth-setup-secret is-veiled is-${veil}${phase === 'clear' ? ' is-clearing' : ''}`}
              aria-label={WORDS.appKeyHead}
              onClick={reveal}
            >
              <span className="auth-key-glitch" data-text={shown}>{shown}</span>
            </button>
          )}
          {open && (
            <button
              type="button"
              className="auth-side-ask"
              aria-expanded={next}
              onClick={() => setNext((openNow) => !openNow)}
            >
              {WORDS.appKeyNext}
            </button>
          )}
        </div>
      )}
      {secret && open && (
        <button type="button" className="auth-key-copy" onClick={copy}>
          {copied ? WORDS.copied : WORDS.appKeyCopy}
        </button>
      )}
      {secret && open && next && (
        <KeyAfter onDone={() => {
          setNext(false)
          focusCode()
        }}
        />
      )}
      {!secret && <p className="auth-help-wait">{WORDS.walkNoSecret}</p>}
      {held && <p className="auth-help-wait">{WORDS.walkHold}</p>}
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
          {WORDS.appKeyCopy}
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

/** Один кадр за раз. Смена шага — сдвиг, как переход между экранами телефона. */
export default function AuthWalk({ onDone, setup = null, expectQr = false }) {
  const [index, setIndex] = useState(0)
  const [dir, setDir] = useState(1)
  const [turned, setTurned] = useState(false)
  const [stuck, setStuck] = useState(false)
  const [zoom, setZoom] = useState(-1)
  const step = AUTH_STEPS[index]
  const last = index === AUTH_STEPS.length - 1
  const zoomStep = zoom >= 0 ? AUTH_STEPS[zoom] : null

  useEffect(() => {
    preloadAuthShots()
  }, [])

  const go = (next) => {
    const clamped = Math.max(0, Math.min(AUTH_STEPS.length - 1, next))
    if (clamped === index) return
    setDir(clamped > index ? 1 : -1)
    setTurned(true)
    setIndex(clamped)
  }

  const finish = () => {
    focusCode()
    onDone?.()
  }

  return (
    <section className="auth-path" aria-label={WORDS.walkTitle}>
      <div className="auth-path-viewport">
        <div
          key={step.id}
          className={`auth-path-stage${turned ? ' is-turn' : ''}`}
          style={{ '--auth-turn': dir > 0 ? '22px' : '-22px' }}
        >
          <button
            type="button"
            className={`auth-path-frame${step.id === 'plus' ? ' is-mark' : ''}`}
            aria-label={`${WORDS.walkTap}: ${step.title}`}
            onClick={() => setZoom(index)}
          >
            <img src={stepSrc(step.file)} alt="" decoding="async" fetchPriority="high" draggable={false} />
          </button>
          <div className="auth-path-line" aria-live="polite">
            <span className="auth-shot-num" aria-hidden="true">{index + 1}</span>
            <span className="design-lines">
              {String(step.line).split('\n').map((line) => line.trim()).filter(Boolean).map((line, lineIndex) => (
                <span key={lineIndex} className="design-line">{line}</span>
              ))}
            </span>
          </div>
          {step.id === 'details' && (
            setup?.totpSecret || expectQr ? (
              <CopyKey
                secret={setup?.totpSecret || ''}
                expectQr={expectQr}
                onNeedKey={() => {
                  focusNamed('key')
                  onDone?.()
                }}
              />
            ) : (
              <p className="auth-help-wait">{WORDS.walkReady}</p>
            )
          )}
        </div>
      </div>
      <div className="auth-path-dots" role="tablist" aria-label={WORDS.walkTitle}>
        {AUTH_STEPS.map((item, dot) => (
          <button
            key={item.id}
            type="button"
            className={`auth-path-dot${dot === index ? ' is-on' : ''}`}
            aria-label={item.title}
            aria-current={dot === index ? 'step' : undefined}
            onClick={() => go(dot)}
          />
        ))}
      </div>
      <div className="auth-path-nav">
        <button type="button" className="auth-path-back" disabled={index === 0} onClick={() => go(index - 1)}>
          {WORDS.walkBack}
        </button>
        <button type="button" className="auth-path-next" onClick={() => (last ? finish() : go(index + 1))}>
          {last ? WORDS.walkDone : WORDS.walkNext}
        </button>
      </div>
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

/** Первый вход: маленькая кнопка открывает QR, магазин и картинки целиком. */
export function EntryHelp({ setup = null, expectQr = false }) {
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

  const revealKey = () => {
    close()
    window.setTimeout(() => focusNamed('key'), motionOff() ? 0 : 240)
  }

  return (
    <>
      <button type="button" className="auth-ask" onClick={() => setOpen(true)}>
        {WORDS.walkAsk}
      </button>
      {open && createPortal(
        <div className={`choice-layer entry-guide-layer auth-walk-layer${leaving ? ' is-leaving' : ''}`} onClick={close}>
          <div className="choice-dim" />
          <div className="choice-sheet-motion">
            <div
              className="choice-sheet entry-guide-sheet auth-help-sheet"
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              onClick={(event) => event.stopPropagation()}
            >
              <p id={titleId} className="choice-sheet-title">{WORDS.walkAsk}</p>
              <div className="entry-guide-body auth-help">
                {setup?.qrDataUrl ? (
                  <figure className="auth-help-qr">
                    <img src={setup.qrDataUrl} alt={WORDS.qrAlt} />
                    <figcaption>{WORDS.walkQrShot}</figcaption>
                  </figure>
                ) : expectQr ? (
                  <p className="auth-help-wait">{WORDS.walkQrWait}</p>
                ) : null}
                <CopyKey
                  secret={setup?.totpSecret || ''}
                  expectQr={expectQr || Boolean(setup?.totpSecret)}
                  onNeedKey={revealKey}
                />
                <StoreLinks />
                <AuthWalk setup={setup} expectQr={expectQr} onDone={close} />
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

