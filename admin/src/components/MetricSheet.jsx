import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useIsPhone } from '../lib/useIsDesktop'
import { useOutsideDismiss } from '../lib/outsideDismiss'
import { barPercents, metricDelta } from '../lib/metricModel'
import { fmt } from '../lib/numberFormat'
import { sheetSwipeDecision, swipeVelocity } from '../lib/sheetSwipe'

const MetricCtx = createContext(null)

const noop = { open() {}, sync() {}, close() {} }

export function useMetricSheet() {
  return useContext(MetricCtx) || noop
}

/**
 * Лист детали метрики. Телефон — снизу, ПК — по центру.
 * open запоминает карточку, sync обновляет её, пока она открыта
 * (живые цифры главной не застывают).
 */
export function MetricSheetProvider({ children }) {
  const openId = useRef(null)
  const specs = useRef(new Map())
  const [tick, setTick] = useState(0)
  const [leaving, setLeaving] = useState(false)

  const api = useRef(null)
  if (!api.current) {
    api.current = {
      open(spec) {
        if (!spec?.id) return
        specs.current.set(spec.id, spec)
        openId.current = spec.id
        setLeaving(false)
        setTick((n) => n + 1)
      },
      sync(spec) {
        if (!spec?.id || openId.current !== spec.id) return
        specs.current.set(spec.id, spec)
        setTick((n) => n + 1)
      },
      close(opts) {
        if (!openId.current) return
        if (opts?.immediate) {
          openId.current = null
          setLeaving(false)
          setTick((n) => n + 1)
          return
        }
        setLeaving(true)
        window.setTimeout(() => {
          openId.current = null
          setLeaving(false)
          setTick((n) => n + 1)
        }, 220)
      },
    }
  }

  const spec = openId.current ? specs.current.get(openId.current) : null

  return (
    <MetricCtx.Provider value={api.current}>
      {children}
      {tick >= 0 && spec ? (
        <MetricSheetView spec={spec} leaving={leaving} onClose={api.current.close} />
      ) : null}
    </MetricCtx.Provider>
  )
}

function MetricSheetView({ spec, leaving, onClose }) {
  const phone = useIsPhone()
  const panelRef = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useOutsideDismiss(true, [panelRef], () => onCloseRef.current())

  const dismissTimer = useRef(0)
  useEffect(() => () => window.clearTimeout(dismissTimer.current), [])

  useEffect(() => {
    if (!phone) return undefined
    const sheet = panelRef.current
    if (!sheet) return undefined
    let drag = null
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches

    const dim = () => sheet.closest('.metric-sheet-root')?.querySelector('.metric-sheet-dim')

    const place = (dy, mode) => {
      sheet.classList.toggle('is-dragging', mode === 'drag')
      sheet.classList.toggle('is-settling', mode === 'back')
      sheet.classList.toggle('is-swipe', mode === 'away')
      if (mode === 'back') sheet.style.transform = 'translate3d(0, 0, 0)'
      else if (dy > 0) sheet.style.transform = `translate3d(0, ${Math.round(dy)}px, 0)`
      else sheet.style.transform = ''
      const veil = dim()
      if (!veil) return
      if (mode === 'drag' && dy > 0) veil.style.opacity = String(Math.max(0, 1 - dy / 280))
      else if (mode === 'away') veil.style.opacity = '0'
      else veil.style.opacity = ''
    }

    const onDown = (event) => {
      if (leaving || (event.button != null && event.button > 0)) return
      if (event.target.closest('button, a, input, textarea, select, [role="option"]')) return
      drag = {
        id: event.pointerId,
        y0: event.clientY,
        samples: [{ y: event.clientY, t: performance.now() }],
        fromGrab: Boolean(event.target.closest('.metric-sheet-grab, .metric-sheet-top')),
        active: false,
      }
      sheet.setPointerCapture?.(event.pointerId)
    }

    const onMove = (event) => {
      if (!drag || event.pointerId !== drag.id) return
      const dy = event.clientY - drag.y0
      const now = performance.now()
      drag.samples.push({ y: event.clientY, t: now })
      drag.samples = drag.samples.filter((sample) => now - sample.t < 90)
      if (!drag.fromGrab && sheet.scrollTop > 2 && !drag.active) return
      if (dy <= 0) {
        if (drag.active) place(0, 'back')
        drag.active = false
        return
      }
      if (!drag.active && dy < 8) return
      drag.active = true
      event.preventDefault()
      place(dy, 'drag')
    }

    const release = (event, cancel) => {
      if (!drag || event.pointerId !== drag.id) return
      const current = drag
      drag = null
      if (!current.active || cancel) {
        place(0, 'back')
        return
      }
      const dy = event.clientY - current.y0
      const height = Math.max(sheet.offsetHeight || 0, 240)
      const decision = sheetSwipeDecision({
        dy,
        velocity: swipeVelocity(current.samples),
        height,
      })
      if (decision === 'close') {
        const off = Math.max(height + 32, Math.round(window.innerHeight * 0.55))
        place(off, 'away')
        window.clearTimeout(dismissTimer.current)
        dismissTimer.current = window.setTimeout(() => {
          onCloseRef.current({ immediate: true })
        }, reduced ? 0 : 320)
        return
      }
      place(0, 'back')
      window.clearTimeout(dismissTimer.current)
      dismissTimer.current = window.setTimeout(() => {
        if (!sheet.classList.contains('is-settling')) return
        sheet.classList.remove('is-settling')
        sheet.style.transform = ''
      }, reduced ? 0 : 340)
    }

    const onUp = (event) => release(event, false)
    const onCancel = (event) => release(event, true)
    sheet.addEventListener('pointerdown', onDown)
    sheet.addEventListener('pointermove', onMove, { passive: false })
    sheet.addEventListener('pointerup', onUp)
    sheet.addEventListener('pointercancel', onCancel)
    return () => {
      sheet.removeEventListener('pointerdown', onDown)
      sheet.removeEventListener('pointermove', onMove)
      sheet.removeEventListener('pointerup', onUp)
      sheet.removeEventListener('pointercancel', onCancel)
    }
  }, [phone, leaving, spec.id])

  useEffect(() => {
    const node = panelRef.current
    const previous = document.activeElement
    node?.focus()
    return () => {
      if (previous && typeof previous.focus === 'function') previous.focus()
    }
  }, [])

  const bars = spec.bars || []
  const percents = barPercents(bars.map((bar) => bar.value))
  const delta = metricDelta(spec.current, spec.previous)
  const tone = delta == null ? '' : delta > 0 ? 'is-up' : delta < 0 ? 'is-down' : ''
  const [focus, setFocus] = useState(0)
  const safeFocus = bars.length ? Math.min(focus, bars.length - 1) : 0
  const active = bars[safeFocus] || null
  const total = bars.reduce((sum, bar) => sum + (Number(bar.value) > 0 ? Number(bar.value) : 0), 0)
  const share = active && total > 0
    ? Math.round(((Number(active.value) > 0 ? Number(active.value) : 0) / total) * 100)
    : 0

  useEffect(() => {
    setFocus(0)
  }, [spec.id])

  return createPortal(
    <div className={`metric-sheet-root${phone ? ' is-phone' : ' is-desk'}${leaving ? ' is-leaving' : ''}`}>
      <span className="metric-sheet-dim" aria-hidden="true" />
      <div
        ref={panelRef}
        className="metric-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={spec.title}
        tabIndex={-1}
      >
        <span className="metric-sheet-grab" aria-hidden="true" />
        <div className="metric-sheet-top">
          <h2>{spec.title}</h2>
          <button type="button" className="metric-sheet-x" onClick={onClose} aria-label="Закрыть">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <p className="metric-sheet-value">
          <strong>{spec.value}</strong>
          {spec.unit ? <span>{spec.unit}</span> : null}
        </p>
        {spec.hint ? <p className="metric-sheet-hint">{spec.hint}</p> : null}
        {delta != null && (
          <p className={`metric-sheet-delta ${tone}`}>
            {delta > 0 ? '+' : ''}
            {fmt(delta)}
            {spec.previousLabel ? ` к «${spec.previousLabel}»` : ' к прошлому периоду'}
          </p>
        )}
        {spec.note ? <p className="metric-sheet-note">{spec.note}</p> : null}
        {bars.length > 0 && (
          <div className="metric-bars" role="listbox" aria-label="Фрагменты аналитики">
            {bars.map((bar, index) => (
              <button
                type="button"
                role="option"
                aria-selected={index === safeFocus}
                className={`metric-bar${index === safeFocus ? ' is-on' : ''}`}
                key={bar.label}
                onMouseEnter={() => setFocus(index)}
                onFocus={() => setFocus(index)}
                onClick={() => setFocus(index)}
              >
                <span className="metric-bar-track">
                  <span className="metric-bar-col" style={{ height: `${percents[index]}%` }} />
                </span>
                <span className="metric-bar-label">{bar.label}</span>
              </button>
            ))}
          </div>
        )}
        {active && (
          <p className="metric-bar-readout" aria-live="polite">
            <strong>{active.label}</strong>
            <span>{fmt(Number(active.value) || 0)}</span>
            <em>{total > 0 ? `${share}% от суммы фрагментов` : 'нет значений'}</em>
          </p>
        )}
        {spec.action && (
          <button
            type="button"
            className="metric-sheet-action"
            onClick={() => {
              spec.action.run?.()
              onClose()
            }}
          >
            {spec.action.label}
          </button>
        )}
      </div>
    </div>,
    document.body,
  )
}

/** Поле, которое открывает лист. Без spec остаётся обычным блоком. */
export function MetricTile({ spec, className = '', disabled = false, children }) {
  const { open } = useMetricSheet()
  if (disabled || !spec) {
    return <div className={className}>{children}</div>
  }
  return (
    <button
      type="button"
      className={`metric-tile${className ? ` ${className}` : ''}`}
      aria-haspopup="dialog"
      onClick={() => open(spec)}
    >
      {children}
      <span className="metric-tile-mark" aria-hidden="true">↗</span>
    </button>
  )
}
