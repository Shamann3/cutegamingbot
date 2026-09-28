import { useEffect, useRef } from 'react'

const GLYPHS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ΣΔΛΞΨΩ<>/{}[]=+*#$'
const ACCENT_POLL_MS = 400

function pickGlyph() {
  return GLYPHS[(Math.random() * GLYPHS.length) | 0]
}

/**
 * Матричный «дождь кода».
 *
 * Один canvas, ограниченный fps, пауза во вкладке в фоне.
 * Колонки падают с разной скоростью и дробным шагом — поэтому движение
 * читается плавным, а не рывками. Цвет перечитывается из акцента палитры,
 * так что смена цвета интерфейса подхватывается на лету.
 */
export default function MatrixRain({
  paused = false,
  className = 'ent-matrix',
  fps = 30,
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (paused) return undefined
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return undefined

    const root = document.documentElement
    let accent = '255, 5, 36'
    let accentAt = 0
    const readAccent = (now) => {
      if (now - accentAt < ACCENT_POLL_MS) return
      accentAt = now
      const next = getComputedStyle(root).getPropertyValue('--e-accent-rgb').trim()
      if (next) accent = next
    }

    let width = 0
    let height = 0
    let cell = 16
    let columns = []

    const makeColumn = (startAbove) => ({
      y: startAbove ? -Math.random() * (height / cell) : 0,
      speed: 0.35 + Math.random() * 0.55,
      glyph: pickGlyph(),
      swaps: 0,
    })

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth || window.innerWidth
      height = canvas.clientHeight || window.innerHeight
      // На узких экранах колонки реже — меньше работы, крупнее рисунок.
      cell = width < 600 ? 19 : 16
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.font = `${cell - 2}px "SFMono-Regular", "JetBrains Mono", Menlo, monospace`
      ctx.textBaseline = 'top'
      const count = Math.max(1, Math.ceil(width / cell))
      const next = new Array(count)
      for (let i = 0; i < count; i += 1) next[i] = columns[i] || makeColumn(true)
      columns = next
      ctx.clearRect(0, 0, width, height)
    }

    resize()
    window.addEventListener('resize', resize)

    let raf = 0
    let last = 0
    const frameMs = 1000 / Math.max(1, fps)

    const draw = (now) => {
      raf = window.requestAnimationFrame(draw)
      if (document.hidden) return
      if (now - last < frameMs) return
      last = now
      readAccent(now)

      // Мягкий шлейф: старые глифы гаснут, а не стираются рывком.
      ctx.fillStyle = 'rgba(0, 0, 0, 0.085)'
      ctx.fillRect(0, 0, width, height)

      const head = `rgba(${accent}, 0.95)`
      const tail = `rgba(${accent}, 0.30)`

      for (let i = 0; i < columns.length; i += 1) {
        const col = columns[i]
        const x = i * cell
        const y = col.y * cell

        // Глиф меняется не каждый кадр — иначе колонка «кипит» и мельтешит.
        col.swaps += 1
        if (col.swaps > 2) {
          col.glyph = pickGlyph()
          col.swaps = 0
        }

        ctx.fillStyle = head
        ctx.fillText(col.glyph, x, y)
        ctx.fillStyle = tail
        ctx.fillText(col.glyph, x, y - cell)

        col.y += col.speed
        if (y > height && Math.random() > 0.96) {
          columns[i] = makeColumn(false)
        }
      }
    }

    raf = window.requestAnimationFrame(draw)

    return () => {
      window.cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [paused, fps])

  if (paused) return null

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
