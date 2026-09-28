import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  clamp,
  defaultAccent,
  hexToRgb,
  hsvToHex,
  normalizeAccent,
  parseHexInput,
  rgbToHsv,
} from '../lib/accentTheme'
import { useOutsideDismiss } from '../lib/outsideDismiss'

const WHEEL_SIZE = 148
const WHEEL_RADIUS = WHEEL_SIZE / 2

function paintWheel(canvas) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const size = WHEEL_SIZE
  canvas.width = size
  canvas.height = size
  canvas.style.width = '100%'
  canvas.style.height = '100%'

  const image = ctx.createImageData(size, size)
  const data = image.data
  const cx = WHEEL_RADIUS
  const cy = WHEEL_RADIUS
  const maxR = WHEEL_RADIUS - 1

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = x - cx
      const dy = y - cy
      const dist = Math.sqrt(dx * dx + dy * dy)
      const i = (y * size + x) * 4
      if (dist > maxR) {
        data[i + 3] = 0
        continue
      }
      let angle = (Math.atan2(dy, dx) * 180) / Math.PI
      if (angle < 0) angle += 360
      const sat = clamp(dist / maxR, 0, 1)
      const hex = hsvToHex(angle, sat, 1)
      data[i] = parseInt(hex.slice(1, 3), 16)
      data[i + 1] = parseInt(hex.slice(3, 5), 16)
      data[i + 2] = parseInt(hex.slice(5, 7), 16)
      data[i + 3] = 255
    }
  }
  ctx.putImageData(image, 0, 0)
}

function pointerToHsv(clientX, clientY, rect, value) {
  const scaleX = WHEEL_SIZE / Math.max(1, rect.width)
  const scaleY = WHEEL_SIZE / Math.max(1, rect.height)
  const x = (clientX - rect.left) * scaleX
  const y = (clientY - rect.top) * scaleY
  const dx = x - WHEEL_RADIUS
  const dy = y - WHEEL_RADIUS
  const dist = Math.sqrt(dx * dx + dy * dy)
  const maxR = WHEEL_RADIUS - 2
  let angle = (Math.atan2(dy, dx) * 180) / Math.PI
  if (angle < 0) angle += 360
  const sat = clamp(dist / maxR, 0, 1)
  return { h: angle, s: sat, v: value }
}

export default function AccentPalette({ value, onChange, inline = false }) {
  const accent = normalizeAccent(value)
  const [open, setOpen] = useState(inline)
  const [leaving, setLeaving] = useState(false)
  const [draft, setDraft] = useState(accent)
  const [hexText, setHexText] = useState(accent.hex)
  const [hexOk, setHexOk] = useState(true)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)
  const dragging = useRef(false)
  const [wheelPx, setWheelPx] = useState(WHEEL_SIZE)
  const rootRef = useRef(null)
  const panelRef = useRef(null)
  const triggerRef = useRef(null)
  const draftRef = useRef(draft)
  const hexTextRef = useRef(hexText)
  const onChangeRef = useRef(onChange)

  draftRef.current = draft
  hexTextRef.current = hexText
  onChangeRef.current = onChange

  const placePanel = useCallback(() => {
    const btn = triggerRef.current
    const panel = panelRef.current
    if (!btn) return
    const r = btn.getBoundingClientRect()
    const gap = 10
    const pw = Math.min(248, window.innerWidth - 24)
    const ph = Math.min(panel?.offsetHeight || 360, window.innerHeight - 24)
    let left = r.right + gap
    let top = r.top

    if (left + pw > window.innerWidth - 12) {
      left = Math.max(12, r.left - gap - pw)
    }
    left = Math.max(12, Math.min(left, window.innerWidth - pw - 12))
    if (top + ph > window.innerHeight - 12) {
      top = Math.max(12, window.innerHeight - ph - 12)
    }
    top = Math.max(12, Math.min(top, window.innerHeight - Math.min(ph, window.innerHeight - 24) - 12))
    setPos({ top, left })
  }, [])

  const pushAccent = useCallback((next) => {
    const normalized = normalizeAccent(next)
    setDraft(normalized)
    setHexText(normalized.hex)
    setHexOk(true)
    onChangeRef.current?.(normalized)
  }, [])

  const paintColor = useCallback((hex) => {
    const current = normalizeAccent(draftRef.current)
    pushAccent(normalizeAccent({
      ...current,
      hex,
      stops: [hex],
      hexSource: true,
      id: 'custom',
      label: 'Свой',
    }))
  }, [pushAccent])

  const commitHsv = useCallback((partial) => {
    const current = normalizeAccent(draftRef.current)
    const { r, g, b } = hexToRgb(current.hex)
    const hsv = rgbToHsv(r, g, b)
    const next = {
      h: partial.h ?? hsv.h,
      s: partial.s ?? hsv.s,
      v: partial.v ?? hsv.v,
    }
    paintColor(hsvToHex(next.h, next.s, next.v))
  }, [paintColor])

  const commitHex = useCallback((raw, { silentInvalid = false } = {}) => {
    const parsed = parseHexInput(raw)
    if (!parsed) {
      setHexOk(false)
      if (!silentInvalid) {
        setHexText(normalizeAccent(draftRef.current).hex)
      }
      return false
    }
    paintColor(parsed)
    return true
  }, [paintColor])

  const closingRef = useRef(false)
  const closePalette = useCallback(() => {
    if (closingRef.current) return
    closingRef.current = true
    commitHex(hexTextRef.current, { silentInvalid: false })
    setLeaving(true)
    window.setTimeout(() => {
      setOpen(false)
      setLeaving(false)
      closingRef.current = false
    }, 180)
  }, [commitHex])

  useEffect(() => {
    if (!open && !inline) return
    const next = normalizeAccent(value)
    setDraft(next)
    setHexText(next.hex)
    setHexOk(true)
  }, [open, inline, value])

  useLayoutEffect(() => {
    if (!open || inline) return undefined
    placePanel()
    const id = window.requestAnimationFrame(() => {
      placePanel()
      window.requestAnimationFrame(placePanel)
    })
    window.addEventListener('resize', placePanel)
    window.addEventListener('scroll', placePanel, true)
    return () => {
      window.cancelAnimationFrame(id)
      window.removeEventListener('resize', placePanel)
      window.removeEventListener('scroll', placePanel, true)
    }
  }, [open, placePanel])

  useEffect(() => {
    if ((!open && !inline) || !canvasRef.current) return
    paintWheel(canvasRef.current)
  }, [open, inline])

  useLayoutEffect(() => {
    const node = wrapRef.current
    if (!node || (!open && !inline)) return undefined
    const measure = () => {
      const next = node.getBoundingClientRect().width
      if (next > 0) setWheelPx(next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [open, inline])

  // Тап мимо палитры закрывает только её. Если тап был ещё и мимо сайдбара,
  // сайдбар закроется своим обработчиком — событие до него доходит.
  useOutsideDismiss(open && !leaving && !inline, [rootRef, panelRef], closePalette)

  const onWheelPointer = (e) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const current = normalizeAccent(draftRef.current)
    const { r, g, b } = hexToRgb(current.hex)
    const hsv = rgbToHsv(r, g, b)
    const rect = canvas.getBoundingClientRect()
    const picked = pointerToHsv(e.clientX, e.clientY, rect, hsv.v)
    commitHsv(picked)
  }

  const onWheelDown = (e) => {
    dragging.current = true
    canvasRef.current?.setPointerCapture?.(e.pointerId)
    onWheelPointer(e)
  }

  const onWheelMove = (e) => {
    if (!dragging.current) return
    onWheelPointer(e)
  }

  const onWheelUp = (e) => {
    dragging.current = false
    try {
      canvasRef.current?.releasePointerCapture?.(e.pointerId)
    } catch {
      /* ignore */
    }
  }

  const activeHex = draft.hex
  const activeRgb = hexToRgb(activeHex)
  const activeHsv = rgbToHsv(activeRgb.r, activeRgb.g, activeRgb.b)

  const resetAll = () => {
    pushAccent(defaultAccent())
  }

  const knobStyle = (() => {
    const rad = (activeHsv.h * Math.PI) / 180
    const knob = 16
    const disk = ((WHEEL_RADIUS - 1) / WHEEL_SIZE) * wheelPx
    const reach = Math.max(0, disk - knob / 2 - 1)
    const dist = clamp(activeHsv.s, 0, 1) * reach
    const x = (wheelPx / 2 + Math.cos(rad) * dist) / wheelPx
    const y = (wheelPx / 2 + Math.sin(rad) * dist) / wheelPx
    return {
      left: `${x * 100}%`,
      top: `${y * 100}%`,
      background: activeHex,
    }
  })()

  const previewHex = parseHexInput(hexText) || activeHex
  const brightPct = Math.round(activeHsv.v * 100)

  const wheel = (
      <div
        ref={panelRef}
        className={`accent-picker-panel${inline ? ' is-inline' : ''}${leaving ? ' is-leaving' : ''}`}
        role="dialog"
        aria-label="Палитра цвета"
        style={inline ? undefined : { top: pos.top, left: pos.left }}
      >
        <div className="accent-wheel-wrap" ref={wrapRef}>
          <canvas
            ref={canvasRef}
            className="accent-wheel"
            onPointerDown={onWheelDown}
            onPointerMove={onWheelMove}
            onPointerUp={onWheelUp}
            onPointerCancel={onWheelUp}
          />
          <span className="accent-wheel-knob" style={knobStyle} aria-hidden />
        </div>

        <div className="accent-picker-side">
        <label className="accent-slider">
          <span>Яркость цвета</span>
          <strong>{brightPct}%</strong>
          <input
            type="range"
            min={0}
            max={100}
            value={brightPct}
            onChange={(e) => commitHsv({ v: Number(e.target.value) / 100 })}
            style={{ '--fill': `${brightPct}%`, '--thumb': activeHex }}
          />
        </label>

        <label className="accent-slider">
          <span>Сила подсветки</span>
          <strong>{Math.round(draft.glow)}%</strong>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(draft.glow)}
            onChange={(e) => {
              const current = normalizeAccent(draftRef.current)
              pushAccent(normalizeAccent({ ...current, glow: Number(e.target.value) }))
            }}
            style={{ '--fill': `${Math.round(draft.glow)}%`, '--thumb': activeHex }}
          />
        </label>

        <div className={`accent-hex-field${hexOk ? '' : ' accent-hex-field-bad'}`}>
          <div className="accent-hex-field-head">
            <span>HEX</span>
            <em>{hexOk ? 'свой цвет' : 'проверьте код'}</em>
          </div>
          <div className="accent-hex-shell">
            <span
              className="accent-hex-preview"
              style={{ background: previewHex }}
              aria-hidden
            />
            <input
              value={hexText}
              onChange={(e) => {
                let raw = e.target.value.trim()
                if (raw && !raw.startsWith('#')) raw = `#${raw}`
                raw = raw.replace(/[^#0-9A-Fa-f]/g, '').slice(0, 7)
                setHexText(raw)
                const parsed = parseHexInput(raw)
                if (parsed) {
                  setHexOk(true)
                  commitHex(parsed)
                } else {
                  setHexOk(raw.length < 4)
                }
              }}
              onBlur={() => {
                commitHex(hexText)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  if (commitHex(hexText)) closePalette()
                }
              }}
              placeholder="#FFFFFF"
              spellCheck={false}
              maxLength={7}
              inputMode="text"
              autoCapitalize="off"
              autoCorrect="off"
              aria-invalid={!hexOk}
              aria-label="HEX-код цвета"
            />
          </div>
        </div>
        </div>

        <div
          className="accent-stops-preview"
          style={{ background: `linear-gradient(100deg, #050508 0%, ${activeHex} 100%)` }}
          aria-hidden="true"
        />

        <label className="accent-slider">
          <span>Прозрачность деталей</span>
          <strong>{Math.round(draft.clear)}%</strong>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(draft.clear)}
            onChange={(e) => {
              const current = normalizeAccent(draftRef.current)
              pushAccent(normalizeAccent({ ...current, clear: Number(e.target.value) }))
            }}
            style={{ '--fill': `${Math.round(draft.clear)}%`, '--thumb': activeHex }}
            aria-label="Прозрачность кнопок и карточек"
          />
        </label>

        <div className="accent-actions">
          <button type="button" className="accent-reset" onClick={resetAll}>
            <i className="accent-reset-mark" aria-hidden="true" />
            <span>Сброс до стандартного цвета</span>
          </button>
        </div>
      </div>
  )

  const panel = (open || leaving) && !inline ? createPortal(
    <>
      {/* Только затемнение: клики проходят насквозь, закрытие — через useOutsideDismiss */}
      <span className={`accent-picker-backdrop${leaving ? ' is-leaving' : ''}`} aria-hidden="true" />
      {wheel}
    </>,
    document.body,
  ) : null

  if (inline) return wheel

  return (
    <div className="accent-picker-root" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="panel-accent-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          if (open) closePalette()
          else setOpen(true)
        }}
      >
        <span
          className="panel-accent-trigger-swatch"
          style={{ background: `linear-gradient(135deg, #050508 0%, ${accent.hex} 100%)` }}
          aria-hidden
        />
        <span className="panel-accent-trigger-meta">
          <strong>Любой цвет</strong>
          <em>{accent.hex}</em>
        </span>
        <span className="panel-accent-trigger-chevron" aria-hidden>{open ? '◂' : '▸'}</span>
      </button>
      {panel}
    </div>
  )
}
