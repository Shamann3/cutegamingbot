/** Тема подсветки: любой оттенок (HSV) + сила свечения. */

export const ACCENT_SWATCHES = [
  { id: 'snow', label: 'Снег', hex: '#FFFFFF' },
  { id: 'ink', label: 'Чёрный', hex: '#000000' },
  { id: 'mint', label: 'Мята', hex: '#7EB89A' },
  { id: 'sky', label: 'Небо', hex: '#6BA3C9' },
  { id: 'violet', label: 'Фиалка', hex: '#9B8BC9' },
  { id: 'rose', label: 'Роза', hex: '#D48A96' },
  { id: 'amber', label: 'Янтарь', hex: '#D4B56A' },
  { id: 'coral', label: 'Коралл', hex: '#E07A5F' },
]

/** Куда ложится свет. Порядок — это порядок в палитре. */
export const SCENES = [
  { id: 'horizon', label: 'Горизонт', hint: 'Свет поднимается снизу' },
  { id: 'eclipse', label: 'Кольцо', hint: 'Сияние в центре экрана' },
  { id: 'beam', label: 'Луч', hint: 'Полоса наискосок' },
  { id: 'corners', label: 'Углы', hint: 'Четыре лампы по краям' },
  { id: 'aurora', label: 'Ленты', hint: 'Широкое сияние сверху' },
  { id: 'tide', label: 'Берега', hint: 'Цвет слева и справа' },
  { id: 'lantern', label: 'Фонарь', hint: 'Один мягкий свет сверху' },
  { id: 'rim', label: 'Кромка', hint: 'Цвет только по краю' },
]

const STORAGE_KEY = 'epsilon.panel.accent.v2'
const DEFAULT_GLOW = 55
const DEFAULT_SCENE = 'horizon'
const DEFAULT_CLEAR = 62
const DEFAULT_ACCENT = ACCENT_SWATCHES[0]

export function defaultAccent() {
  const rgb = hexToRgb(DEFAULT_ACCENT.hex)
  const hsv = rgbToHsv(rgb.r, rgb.g, rgb.b)
  return {
    ...DEFAULT_ACCENT,
    ...hsv,
    glow: DEFAULT_GLOW,
    stops: [DEFAULT_ACCENT.hex],
    scene: DEFAULT_SCENE,
    clear: DEFAULT_CLEAR,
  }
}

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

/** Белый текст только на тёмном акценте, где он держит контраст 4.5:1. */
const INK_LUMINANCE = 0.18

/** Чёрный текст на светлом акценте, белый — на тёмном */
export function inkOnAccent(hex) {
  return relativeLuminance(hex) > INK_LUMINANCE ? '#111111' : '#ffffff'
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

export const MAX_STOPS = 4

/** До четырёх цветов, которые человек сам выбрал. */
export function sanitizeStops(raw, fallbackHex) {
  const list = []
  if (Array.isArray(raw)) {
    for (const item of raw) {
      const hex = parseHexInput(typeof item === 'string' ? item : item?.hex)
      if (!hex) continue
      list.push(hex)
      if (list.length >= MAX_STOPS) break
    }
  }
  if (!list.length && fallbackHex) list.push(fallbackHex)
  return list
}

function hsvOfHex(hex) {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHsv(r, g, b)
}

/**
 * Делает цвет фоном, на который приятно смотреть.
 * Бледный первый цвет остаётся лампой. Остальные сдвиги — уже насыщенные.
 */
function isInk(hex) {
  return hsvOfHex(hex).v < 0.08
}

function bloom(hex, shift = 0) {
  if (isInk(hex)) return '#000000'
  const hsv = hsvOfHex(hex)
  const pale = hsv.s < 0.14
  if (pale && shift === 0) {
    return hsvToHex(hsv.h, Math.min(hsv.s, 0.08), Math.max(hsv.v, 0.94))
  }
  const h = (((pale ? 262 : hsv.h) + shift) % 360 + 360) % 360
  const s = pale ? 0.9 : Math.min(1, Math.max(hsv.s, 0.84))
  const v = pale ? 0.96 : Math.min(1, Math.max(hsv.v, 0.74))
  return hsvToHex(h, s, v)
}

function readScene(input) {
  const id = input && typeof input === 'object' ? input.scene : ''
  return SCENES.some((scene) => scene.id === id) ? id : DEFAULT_SCENE
}

function readClear(input) {
  const raw = input && typeof input === 'object' ? input.clear : undefined
  return Number.isFinite(raw) ? clamp(raw, 0, 100) : DEFAULT_CLEAR
}

const FILL_SHIFTS = [34, 186, 308]

export function normalizeAccent(input) {
  if (!input) return defaultAccent()

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

  const storedStops = input && typeof input === 'object' ? input.stops : null
  let stops = sanitizeStops(storedStops, finalHex)
  if (input?.hexSource) {
    stops = [finalHex, ...stops.slice(1)].slice(0, MAX_STOPS)
  } else if (Array.isArray(storedStops) && stops[0]) {
    finalHex = stops[0]
    const locked = hexToRgb(finalHex)
    const fromStop = rgbToHsv(locked.r, locked.g, locked.b)
    h = fromStop.h
    s = fromStop.s
    v = fromStop.v
  }
  if (!stops.length) stops = [finalHex]

  const known = ACCENT_SWATCHES.find((sw) => sw.hex.toLowerCase() === finalHex.toLowerCase())
  return {
    id: known ? known.id : id === 'custom' || !known ? 'custom' : id,
    label: known ? known.label : label,
    hex: finalHex,
    h,
    s,
    v,
    glow,
    stops,
    scene: readScene(input),
    clear: readClear(input),
  }
}

/** Четыре ярких точки фона: выбранные цвета и, если их меньше, соседи по кругу. */
export function gradientStopsFrom(accent) {
  const base = normalizeAccent(accent)
  const chosen = base.stops.length ? base.stops : [base.hex]
  if (chosen.every(isInk)) {
    const dark = chosen.map(() => '#000000')
    while (dark.length < MAX_STOPS) dark.push('#000000')
    return dark.slice(0, MAX_STOPS)
  }
  const painted = chosen.map((hex) => bloom(hex, 0))
  const seed = chosen.find((hex) => !isInk(hex)) || chosen[0]
  let fill = 0
  while (painted.length < MAX_STOPS && fill < FILL_SHIFTS.length) {
    painted.push(bloom(seed, FILL_SHIFTS[fill]))
    fill += 1
  }
  return painted.slice(0, MAX_STOPS)
}

/** Следующий цвет, который ещё не выбран: яркий сосед, а не копия. */
export function suggestNextStop(stops) {
  const list = sanitizeStops(stops, DEFAULT_ACCENT.hex)
  const painted = gradientStopsFrom({ hex: list[0], stops: list })
  const used = new Set(list.map((hex) => hex.toLowerCase()))
  return painted.find((hex) => !used.has(hex.toLowerCase())) || painted[Math.min(list.length, MAX_STOPS - 1)]
}

/** @deprecated use normalizeAccent */
export function resolveAccent(idOrHex) {
  return normalizeAccent(idOrHex)
}

export function applyAccentToDocument(accent, { flash = false } = {}) {
  if (typeof document === 'undefined') return
  const a = normalizeAccent(accent)
  const { r, g, b } = hexToRgb(a.hex)
  const glow = a.glow / 100
  const soft = 0.22 + glow * 0.42
  const soft2 = 0.34 + glow * 0.48
  const line = 0.55 + glow * 0.4
  const glowPx = 28 + glow * 72
  const glowAlpha = 0.22 + glow * 0.48
  const ink = inkOnAccent(a.hex)
  const brightToward = relativeLuminance(a.hex) > INK_LUMINANCE ? '#000000' : '#ffffff'
  const brightAmt = relativeLuminance(a.hex) > INK_LUMINANCE ? 0.22 : 0.28

  const painted = gradientStopsFrom(a)
  const root = document.documentElement
  painted.forEach((hex, index) => {
    const rgb = hexToRgb(hex)
    root.style.setProperty(`--e-g${index + 1}`, `${rgb.r}, ${rgb.g}, ${rgb.b}`)
  })
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
  root.style.setProperty('--e-accent-wash', `rgba(${r}, ${g}, ${b}, ${(0.14 + glow * 0.28).toFixed(3)})`)
  root.style.setProperty('--e-accent-ring', `rgba(${r}, ${g}, ${b}, ${(0.45 + glow * 0.35).toFixed(3)})`)
  root.style.setProperty('--ent-accent', a.hex)
  root.style.setProperty('--ent-accent-rgb', `${r}, ${g}, ${b}`)
  root.dataset.accent = a.id
  root.dataset.accentInk = ink === '#111111' ? 'dark' : 'light'
  root.dataset.scene = a.scene
  root.style.setProperty('--e-glass', ((100 - a.clear) / 100).toFixed(3))
  root.style.setProperty('--e-clear', String(a.clear))
  // Flash только при ручной смене палитры — не на первом paint (иначе двери на мгновение «пустые»).
  window.clearTimeout(root._accentFlashTimer)
  if (flash) {
    root.classList.add('accent-changing')
    root._accentFlashTimer = window.setTimeout(() => {
      root.classList.remove('accent-changing')
    }, 900)
  } else {
    root.classList.remove('accent-changing')
  }
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

/** Человек сам менял палитру, и это не белый/серый.
 *  Иначе крепость остаётся чёрно-белой. */
export function accentIsPersonal(accent = loadStoredAccent()) {
  try {
    if (!localStorage.getItem(STORAGE_KEY)) return false
  } catch {
    return false
  }
  const a = normalizeAccent(accent)
  if (a.s >= 0.08) return true
  return a.stops.some((hex) => hsvOfHex(hex).s >= 0.08)
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
        stops: resolved.stops,
        scene: resolved.scene,
        clear: resolved.clear,
      }),
    )
  } catch {
    /* ignore */
  }
  return resolved
}
