import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useIsPhone } from '../lib/useIsDesktop'
import { useOutsideDismiss } from '../lib/outsideDismiss'
import { barPercents, metricDelta } from '../lib/metricModel'
import { fmt } from '../lib/numberFormat'

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
      close() {
        if (!openId.current) return
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

  useEffect(() => {
    const node = panelRef.current
    const previous = document.activeElement
    node?.focus()
    return () => {
      if (previous && typeof previous.focus === 'function') previous.focus()
    }
  }, [])

  const percents = barPercents((spec.bars || []).map((bar) => bar.value))
  const delta = metricDelta(spec.current, spec.previous)
  const tone = delta == null ? '' : delta > 0 ? 'is-up' : delta < 0 ? 'is-down' : ''

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
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
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
        {spec.bars?.length > 0 && (
          <div className="metric-bars" aria-hidden="true">
            {spec.bars.map((bar, index) => (
              <div className="metric-bar" key={bar.label}>
                <span className="metric-bar-track">
                  <span className="metric-bar-col" style={{ height: `${percents[index]}%` }} />
                </span>
                <span className="metric-bar-label">{bar.label}</span>
              </div>
            ))}
          </div>
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
