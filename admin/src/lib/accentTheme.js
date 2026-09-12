/** Тема подсветки: любой оттенок (HSV) + сила свечения. */

export const ACCENT_SWATCHES = [
  { id: 'snow', label: 'Снег', hex: '#FFFFFF' },
  { id: 'mint', label: 'Мята', hex: '#7EB89A' },
  { id: 'sky', label: 'Небо', hex: '#6BA3C9' },
  { id: 'violet', label: 'Фиалка', hex: '#9B8BC9' },
  { id: 'rose', label: 'Роза', hex: '#D48A96' },
  { id: 'amber', label: 'Янтарь', hex: '#D4B56A' },
  { id: 'coral', label: 'Коралл', hex: '#E07A5F' },
]

const STORAGE_KEY = 'epsilon.panel.accent.v2'
const DEFAULT_GLOW = 55
const DEFAULT_ACCENT = ACCENT_SWATCHES[0]

export function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

export function hexToRgb(hex) {
  const h = String(hex || '').replace('#', '').trim()
  if (h.length !== 6) return { r: 255, g: 255, b: 255 }
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

export function rgbToHex(r, g, b) {
  const toHex = (n) => clamp(Math.round(n), 0, 255).toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

/** Нормализация ввода HEX: #abc / abc / #aabbcc */
export function parseHexInput(raw) {
  let s = String(raw || '').trim().replace(/^#/, '')
  if (/^[0-9A-Fa-f]{3}$/.test(s)) {
    s = `${s[0]}${s[0]}${s[1]}${s[1]}${s[2]}${s[2]}`
  }
  if (!/^[0-9A-Fa-f]{6}$/.test(s)) return null
  return `#${s.toLowerCase()}`
}

export function relativeLuminance(hex) {
  const { r, g, b } = hexToRgb(hex)
  const lin = (c) => {
    const x = c / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

/** Чёрный текст на светлом акценте, белый — на тёмном */
export function inkOnAccent(hex) {
  return relativeLuminance(hex) > 0.58 ? '#111111' : '#ffffff'
}

export function rgbToHsv(r, g, b) {
  r /= 255
  g /= 255
  b /= 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  let h = 0
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h *= 60
    if (h < 0) h += 360
  }
  const s = max === 0 ? 0 : d / max
  return { h, s, v: max }
}

export function hsvToRgb(h, s, v) {
  const c = v * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = v - c
  let r = 0
  let g = 0
  let b = 0
  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255),
  }
}

export function hsvToHex(h, s, v) {
  const { r, g, b } = hsvToRgb(h, s, v)
  return rgbToHex(r, g, b)
}

function mixToward(hex, toward = '#ffffff', amount = 0.35) {
  const a = hexToRgb(hex)
  const b = hexToRgb(toward)
  const m = (x, y) => Math.round(x + (y - x) * amount)
  return rgbToHex(m(a.r, b.r), m(a.g, b.g), m(a.b, b.b))
}

export function normalizeAccent(input) {
  if (!input) {
    const base = DEFAULT_ACCENT
    const rgb = hexToRgb(base.hex)
    const hsv = rgbToHsv(rgb.r, rgb.g, rgb.b)
    return { ...base, ...hsv, glow: DEFAULT_GLOW }
  }

  let hex = input.hex
  let id = input.id || 'custom'
  let label = input.label || 'Свой'

  if (!hex && input.id) {
    const sw = ACCENT_SWATCHES.find((s) => s.id === input.id)
    if (sw) {
      hex = sw.hex
      id = sw.id
      label = sw.label
    }
  }

  if (typeof input === 'string') {
    const sw = ACCENT_SWATCHES.find((s) => s.id === input)
    if (sw) {
      hex = sw.hex
      id = sw.id
      label = sw.label
    } else {
      const parsed = parseHexInput(input)
      if (parsed) {
        hex = parsed
        id = 'custom'
        label = 'Свой'
      }
    }
  }

  if (!hex || !/^#[0-9A-Fa-f]{6}$/i.test(hex)) {
    const parsed = parseHexInput(hex)
    if (parsed) hex = parsed
    else {
      hex = DEFAULT_ACCENT.hex
      id = DEFAULT_ACCENT.id
      label = DEFAULT_ACCENT.label
    }
  }

  const normalizedHex = parseHexInput(hex) || String(hex).toLowerCase()
  const rgb = hexToRgb(normalizedHex)
  const fromHex = rgbToHsv(rgb.r, rgb.g, rgb.b)
  const hasHsv =
    Number.isFinite(input?.h) && Number.isFinite(input?.s) && Number.isFinite(input?.v)

  // hexSource: HEX — источник истины (ручной ввод). Иначе HSV от колеса/слайдера.
  let h
  let s
  let v
  let finalHex
  if (input?.hexSource || !hasHsv) {
    h = fromHex.h
    s = fromHex.s
    v = fromHex.v
    finalHex = normalizedHex
  } else {
    h = clamp(input.h, 0, 360)
    s = clamp(input.s, 0, 1)
    v = clamp(input.v, 0, 1)
    finalHex = hsvToHex(h, s, v)
  }

  const glow = Number.isFinite(input?.glow) ? clamp(input.glow, 0, 100) : DEFAULT_GLOW

  const known = ACCENT_SWATCHES.find((sw) => sw.hex.toLowerCase() === finalHex.toLowerCase())
  return {
    id: known ? known.id : id === 'custom' || !known ? 'custom' : id,
    label: known ? known.label : label,
    hex: finalHex,
    h,
    s,
    v,
    glow,
  }
}

/** @deprecated use normalizeAccent */
export function resolveAccent(idOrHex) {
  return normalizeAccent(idOrHex)
}

export function applyAccentToDocument(accent) {
  if (typeof document === 'undefined') return
  const a = normalizeAccent(accent)
  const { r, g, b } = hexToRgb(a.hex)
  const glow = a.glow / 100
  const soft = 0.08 + glow * 0.18
  const soft2 = 0.16 + glow * 0.28
  const line = 0.28 + glow * 0.35
  const glowPx = 18 + glow * 48
  const glowAlpha = 0.08 + glow * 0.28
  const ink = inkOnAccent(a.hex)
  const brightToward = relativeLuminance(a.hex) > 0.58 ? '#000000' : '#ffffff'
  const brightAmt = relativeLuminance(a.hex) > 0.58 ? 0.22 : 0.28

  const root = document.documentElement
  root.style.setProperty('--e-accent', a.hex)
  root.style.setProperty('--e-accent-rgb', `${r}, ${g}, ${b}`)
  root.style.setProperty('--e-accent-soft', `rgba(${r}, ${g}, ${b}, ${soft.toFixed(3)})`)
  root.style.setProperty('--e-accent-soft-2', `rgba(${r}, ${g}, ${b}, ${soft2.toFixed(3)})`)
  root.style.setProperty('--e-accent-line', `rgba(${r}, ${g}, ${b}, ${line.toFixed(3)})`)
  root.style.setProperty('--e-accent-glow', `0 0 ${glowPx.toFixed(0)}px rgba(${r}, ${g}, ${b}, ${glowAlpha.toFixed(3)})`)
  root.style.setProperty('--e-accent-bright', mixToward(a.hex, brightToward, brightAmt))
  root.style.setProperty('--e-accent-ink', ink)
  root.style.setProperty('--e-accent-on', ink)
  root.style.setProperty('--e-accent-glow-strength', String(glow))
  root.style.setProperty('--ent-accent', a.hex)
  root.style.setProperty('--ent-accent-rgb', `${r}, ${g}, ${b}`)
  root.dataset.accent = a.id
  root.dataset.accentInk = ink === '#111111' ? 'dark' : 'light'
}

export function loadStoredAccent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return normalizeAccent(DEFAULT_ACCENT)
    return normalizeAccent(JSON.parse(raw))
  } catch {
    return normalizeAccent(DEFAULT_ACCENT)
  }
}

export function persistAccent(accent) {
  const resolved = normalizeAccent(accent)
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        id: resolved.id,
        hex: resolved.hex,
        h: resolved.h,
        s: resolved.s,
        v: resolved.v,
        glow: resolved.glow,
        label: resolved.label,
      }),
    )
  } catch {
    /* ignore */
  }
  return resolved
}
