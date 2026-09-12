import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  clamp,
  hexToRgb,
  hsvToHex,
  normalizeAccent,
  parseHexInput,
  rgbToHsv,
} from '../lib/accentTheme'

const WHEEL_SIZE = 196
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

function accentFromHex(hex, glow) {
  const parsed = parseHexInput(hex)
  if (!parsed) return null
  const { r, g, b } = hexToRgb(parsed)
  const hsv = rgbToHsv(r, g, b)
  return normalizeAccent({
    hex: parsed,
    ...hsv,
    glow,
    id: 'custom',
    label: 'Свой',
    hexSource: true,
  })
}

export default function AccentPalette({ value, onChange }) {
  const accent = normalizeAccent(value)
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(accent)
  const [hexText, setHexText] = useState(accent.hex)
  const [hexOk, setHexOk] = useState(true)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const canvasRef = useRef(null)
  const dragging = useRef(false)
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
    const pw = panel?.offsetWidth || 236
    const ph = panel?.offsetHeight || 380
    let left = r.right + gap
    let top = r.top + r.height / 2 - ph / 2

    if (left + pw > window.innerWidth - 12) {
      left = Math.max(12, r.left - gap - pw)
    }
    top = Math.max(12, Math.min(top, window.innerHeight - ph - 12))
    setPos({ top, left })
  }, [])

  const pushAccent = useCallback((next) => {
    setDraft(next)
    setHexText(next.hex)
    setHexOk(true)
    onChangeRef.current?.(next)
  }, [])

  const commitHsv = useCallback((partial) => {
    const next = normalizeAccent({ ...draftRef.current, ...partial, hexSource: false })
    pushAccent(next)
  }, [pushAccent])

  const commitHex = useCallback((raw, { silentInvalid = false } = {}) => {
    const next = accentFromHex(raw, draftRef.current.glow)
    if (!next) {
      setHexOk(false)
      if (!silentInvalid) setHexText(draftRef.current.hex)
      return false
    }
    pushAccent(next)
    return true
  }, [pushAccent])

  const closePalette = useCallback(() => {
    commitHex(hexTextRef.current, { silentInvalid: false })
    setOpen(false)
  }, [commitHex])

  useEffect(() => {
    if (!open) return
    const next = normalizeAccent(value)
    setDraft(next)
    setHexText(next.hex)
    setHexOk(true)
  }, [open, value])

  useLayoutEffect(() => {
    if (!open) return undefined
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
    if (!open || !canvasRef.current) return
    paintWheel(canvasRef.current)
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') closePalette()
    }
    const onDown = (e) => {
      if (rootRef.current?.contains(e.target) || panelRef.current?.contains(e.target)) return
      closePalette()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onDown)
    }
  }, [open, closePalette])

  const onWheelPointer = (e) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const hsv = pointerToHsv(e.clientX, e.clientY, rect, draftRef.current.v)
    commitHsv(hsv)
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

  const previewHex = parseHexInput(hexText) || draft.hex

  const panel = open
    ? createPortal(
      <div
        ref={panelRef}
        className="accent-picker-panel"
        role="dialog"
        aria-label="Палитра подсветки"
        style={{ top: pos.top, left: pos.left }}
      >
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
            onChange={(e) => commitHsv({ v: Number(e.target.value) / 100 })}
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
            onChange={(e) => commitHsv({ glow: Number(e.target.value) })}
            style={{ '--fill': `${Math.round(draft.glow)}%`, '--thumb': draft.hex }}
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
              placeholder="#7EB89A"
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
      </div>,
      document.body,
    )
    : null

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
        <span className="panel-accent-trigger-swatch" style={{ background: accent.hex }} aria-hidden />
        <span className="panel-accent-trigger-meta">
          <strong>Подсветка</strong>
          <em>{accent.label === 'Свой' ? accent.hex : accent.label}</em>
        </span>
        <span className="panel-accent-trigger-chevron" aria-hidden>{open ? '◂' : '▸'}</span>
      </button>
      {panel}
    </div>
  )
}
