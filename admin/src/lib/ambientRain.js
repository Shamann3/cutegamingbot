/**
 * Фоновый «дождь» за панелями: редкие потоки глифов в верхней полосе экрана.
 *
 * Логика отделена от canvas: профиль, раскладка потоков и шаг времени —
 * чистые функции, их проверяют тесты. Рисование — одна функция поверх 2D-контекста.
 */

export const AMBIENT_GLYPHS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ΣΔΛΞΨΩ'

const PROFILES = {
  phone: { fps: 12, density: 0.3, cell: 16, dprCap: 1.5, band: 0.44 },
  desktop: { fps: 16, density: 0.22, cell: 15, dprCap: 1.5, band: 0.4 },
}

/**
 * null — только статичный градиент, без анимации.
 * Анимация выключается при системном «уменьшить движение», при явной
 * оптимизации интерфейса и на совсем слабом железе.
 */
export function pickAmbientProfile({
  reducedMotion = false,
  calm = false,
  cores = 0,
  memory = 0,
  phone = false,
} = {}) {
  if (reducedMotion || calm) return null
  if ((cores > 0 && cores <= 2) || (memory > 0 && memory <= 1)) return null
  return { ...(phone ? PROFILES.phone : PROFILES.desktop) }
}

function pick(random) {
  return AMBIENT_GLYPHS[Math.floor(random() * AMBIENT_GLYPHS.length) % AMBIENT_GLYPHS.length]
}

function spawn(stream, rows, cols, taken, random, fresh) {
  let col = Math.floor(random() * cols)
  for (let tries = 0; tries < 6 && taken.has(col); tries += 1) {
    col = Math.floor(random() * cols)
  }
  taken.delete(stream.col)
  taken.add(col)
  stream.col = col
  stream.len = 5 + Math.floor(random() * 7)
  stream.speed = 2.6 + random() * 3.4
  stream.alpha = 0.55 + random() * 0.45
  // Первый кадр: потоки уже разбросаны по полосе, а не стартуют разом сверху.
  stream.y = fresh ? random() * (rows + stream.len) : -random() * rows * 0.7
  stream.glyphs = Array.from({ length: rows + stream.len + 2 }, () => pick(random))
  return stream
}

export function createRain({ width, height, cell, density, random = Math.random }) {
  const cols = Math.max(1, Math.floor(width / cell))
  const rows = Math.max(1, Math.ceil(height / cell))
  const count = Math.max(3, Math.min(cols, Math.round(cols * density)))
  const taken = new Set()
  const streams = []
  for (let i = 0; i < count; i += 1) {
    streams.push(spawn({ col: -1 }, rows, cols, taken, random, true))
  }
  return { width, height, cell, cols, rows, streams, taken }
}

/** Сдвиг во времени; dt в секундах, не больше четверти секунды за шаг. */
export function stepRain(state, dt, random = Math.random) {
  const step = Math.min(Math.max(dt, 0), 0.25)
  for (const s of state.streams) {
    s.y += s.speed * step
    if (random() < 0.12) {
      const i = Math.floor(random() * s.glyphs.length) % s.glyphs.length
      s.glyphs[i] = pick(random)
    }
    if (s.y - s.len > state.rows + 1) {
      spawn(s, state.rows, state.cols, state.taken, random, false)
    }
  }
  return state
}

/** Яркость глифа: голова ярче хвоста, к низу полосы всё гаснет. */
export function glyphAlpha(k, len, row, rows, streamAlpha) {
  if (k < 0 || k >= len || row < 0) return 0
  const tail = k === 0 ? 1 : 0.62 * (1 - k / len)
  const fade = Math.max(0, 1 - row / rows)
  return tail * fade * fade * streamAlpha
}

export function drawRain(ctx, state, rgb, strength = 1) {
  const { cell, rows, streams } = state
  ctx.clearRect(0, 0, state.width, state.height)
  ctx.fillStyle = `rgb(${rgb})`
  for (const s of streams) {
    const head = Math.floor(s.y)
    const x = s.col * cell + cell / 2
    for (let k = 0; k < s.len; k += 1) {
      const row = head - k
      if (row < 0 || row > rows) continue
      const a = glyphAlpha(k, s.len, row, rows, s.alpha) * strength
      if (a < 0.02) continue
      ctx.globalAlpha = a
      ctx.fillText(s.glyphs[row % s.glyphs.length], x, row * cell)
    }
  }
  ctx.globalAlpha = 1
}
