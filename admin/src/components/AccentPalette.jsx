import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ACCENT_SWATCHES,
  clamp,
  hsvToHex,
  normalizeAccent,
} from '../lib/accentTheme'

const WHEEL_SIZE = 200
const WHEEL_RADIUS = WHEEL_SIZE / 2

function paintWheel(canvas) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const size = WHEEL_SIZE
  canvas.width = size
  canvas.height = size
  canvas.style.width = `${size}px`
  canvas.style.height = `${size}px`

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
  const x = clientX - rect.left
  const y = clientY - rect.top
  const dx = x - WHEEL_RADIUS
  const dy = y - WHEEL_RADIUS
  const dist = Math.sqrt(dx * dx + dy * dy)
  const maxR = WHEEL_RADIUS - 2
  let angle = (Math.atan2(dy, dx) * 180) / Math.PI
  if (angle < 0) angle += 360
  const sat = clamp(dist / maxR, 0, 1)
  return { h: angle, s: sat, v: value }
}

export default function AccentPalette({ value, onChange }) {
  const accent = normalizeAccent(value)
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(accent)
  const [hexText, setHexText] = useState(accent.hex)
  const canvasRef = useRef(null)
  const dragging = useRef(false)
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const next = normalizeAccent(value)
    setDraft(next)
    setHexText(next.hex)
  }, [open, value])

  useEffect(() => {
    if (!open || !canvasRef.current) return
    paintWheel(canvasRef.current)
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onDown = (e) => {
      if (!panelRef.current?.contains(e.target) && !e.target.closest?.('.panel-accent-trigger')) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onDown)
    }
  }, [open])

  const commit = useCallback((partial) => {
    const next = normalizeAccent({ ...draft, ...partial })
    setDraft(next)
    setHexText(next.hex)
    onChange?.(next)
  }, [draft, onChange])

  const onWheelPointer = (e) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const hsv = pointerToHsv(e.clientX, e.clientY, rect, draft.v)
    commit(hsv)
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

  const knobStyle = (() => {
    const rad = (draft.h * Math.PI) / 180
    const r = draft.s * (WHEEL_RADIUS - 6)
    return {
      left: `${WHEEL_RADIUS + Math.cos(rad) * r}px`,
      top: `${WHEEL_RADIUS + Math.sin(rad) * r}px`,
      background: draft.hex,
    }
  })()

  return (
    <div className="accent-picker-root" ref={panelRef}>
      <button
        type="button"
        className="panel-accent-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="panel-accent-trigger-swatch" style={{ background: accent.hex }} aria-hidden />
        <span className="panel-accent-trigger-meta">
          <strong>Подсветка</strong>
          <em>{accent.label === 'Свой' ? accent.hex : accent.label}</em>
        </span>
        <span className="panel-accent-trigger-chevron" aria-hidden>{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="accent-picker-panel" role="dialog" aria-label="Палитра подсветки">
          <div className="accent-picker-preview" style={{ '--preview': draft.hex }}>
            <div className="accent-picker-preview-orb" />
            <div className="accent-picker-preview-meta">
              <strong>{draft.hex.toUpperCase()}</strong>
              <span>яркость свечения {Math.round(draft.glow)}%</span>
            </div>
          </div>

          <div className="accent-wheel-wrap">
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

          <label className="accent-slider">
            <span>Яркость цвета</span>
            <strong>{Math.round(draft.v * 100)}%</strong>
            <input
              type="range"
              min={12}
              max={100}
              value={Math.round(draft.v * 100)}
              onChange={(e) => commit({ v: Number(e.target.value) / 100 })}
              style={{ '--fill': `${Math.round(draft.v * 100)}%`, '--thumb': draft.hex }}
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
              onChange={(e) => commit({ glow: Number(e.target.value) })}
              style={{ '--fill': `${Math.round(draft.glow)}%`, '--thumb': draft.hex }}
            />
          </label>

          <label className="accent-hex-field">
            <span>HEX</span>
            <input
              value={hexText}
              onChange={(e) => {
                const raw = e.target.value.trim()
                setHexText(raw)
                if (/^#[0-9A-Fa-f]{6}$/.test(raw)) commit({ hex: raw, id: 'custom', label: 'Свой' })
              }}
              spellCheck={false}
              maxLength={7}
            />
          </label>

          <div className="accent-palette-grid accent-palette-grid-compact">
            {ACCENT_SWATCHES.map((swatch) => {
              const on = draft.hex.toLowerCase() === swatch.hex.toLowerCase()
              return (
                <button
                  key={swatch.id}
                  type="button"
                  className={`accent-swatch${on ? ' accent-swatch-on' : ''}`}
                  style={{ '--swatch': swatch.hex }}
                  title={swatch.label}
                  aria-label={swatch.label}
                  aria-pressed={on}
                  onClick={() => commit({ ...swatch, glow: draft.glow })}
                >
                  <span className="accent-swatch-core" />
                </button>
              )
            })}
          </div>

          <p className="accent-picker-hint">
            Круг — оттенок и насыщенность. Ползунки — яркость цвета и сила свечения по всей панели.
          </p>
        </div>
      )}
    </div>
  )
}
