/** Палитра подсветки админ-панели — пишется в CSS-переменные на :root. */

export const ACCENT_SWATCHES = [
  { id: 'mint', label: 'Мята', hex: '#7EB89A' },
  { id: 'sky', label: 'Небо', hex: '#6BA3C9' },
  { id: 'violet', label: 'Фиалка', hex: '#9B8BC9' },
  { id: 'rose', label: 'Роза', hex: '#D48A96' },
  { id: 'amber', label: 'Янтарь', hex: '#D4B56A' },
  { id: 'coral', label: 'Коралл', hex: '#E07A5F' },
  { id: 'ice', label: 'Лёд', hex: '#A8C5D4' },
  { id: 'pearl', label: 'Жемчуг', hex: '#E8E6E3' },
]

const STORAGE_KEY = 'epsilon.panel.accent'

function hexToRgb(hex) {
  const h = String(hex || '').replace('#', '').trim()
  if (h.length !== 6) return { r: 126, g: 184, b: 154 }
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

function mixToward(hex, toward = '#ffffff', amount = 0.35) {
  const a = hexToRgb(hex)
  const b = hexToRgb(toward)
  const m = (x, y) => Math.round(x + (y - x) * amount)
  const toHex = (n) => n.toString(16).padStart(2, '0')
  return `#${toHex(m(a.r, b.r))}${toHex(m(a.g, b.g))}${toHex(m(a.b, b.b))}`
}

export function resolveAccent(idOrHex) {
  const byId = ACCENT_SWATCHES.find((s) => s.id === idOrHex)
  if (byId) return byId
  if (typeof idOrHex === 'string' && /^#[0-9A-Fa-f]{6}$/.test(idOrHex)) {
    return { id: 'custom', label: 'Свой', hex: idOrHex }
  }
  return ACCENT_SWATCHES[0]
}

export function applyAccentToDocument(accent) {
  if (typeof document === 'undefined') return
  const { hex } = resolveAccent(accent?.id || accent?.hex || accent)
  const { r, g, b } = hexToRgb(hex)
  const root = document.documentElement
  root.style.setProperty('--e-accent', hex)
  root.style.setProperty('--e-accent-rgb', `${r}, ${g}, ${b}`)
  root.style.setProperty('--e-accent-soft', `rgba(${r}, ${g}, ${b}, 0.16)`)
  root.style.setProperty('--e-accent-soft-2', `rgba(${r}, ${g}, ${b}, 0.28)`)
  root.style.setProperty('--e-accent-line', `rgba(${r}, ${g}, ${b}, 0.42)`)
  root.style.setProperty('--e-accent-glow', `0 0 40px rgba(${r}, ${g}, ${b}, 0.22)`)
  root.style.setProperty('--e-accent-bright', mixToward(hex, '#ffffff', 0.28))
  root.dataset.accent = resolveAccent(accent?.id || accent).id
}

export function loadStoredAccent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return ACCENT_SWATCHES[0]
    const parsed = JSON.parse(raw)
    return resolveAccent(parsed?.id || parsed?.hex || raw)
  } catch {
    return ACCENT_SWATCHES[0]
  }
}

export function persistAccent(accent) {
  const resolved = resolveAccent(accent?.id || accent?.hex || accent)
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: resolved.id, hex: resolved.hex }))
  } catch {
    /* ignore */
  }
  return resolved
}
