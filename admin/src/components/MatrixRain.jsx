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
 *
 * prewarm — сколько кадров просчитать до первого показа: для коротких
 * экранов дождь виден сразу по всей высоте, а не «начинается» сверху.
 */
export default function MatrixRain({
  paused = false,
  className = 'ent-matrix',
  fps = 30,
  prewarm = 0,
  density = 1,
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
    let accentAt = -Infinity
    const readAccent = (now) => {
      if (now - accentAt < ACCENT_POLL_MS) return
      accentAt = now
      const next = (
        getComputedStyle(root).getPropertyValue('--e-accent-decor-rgb')
        || getComputedStyle(root).getPropertyValue('--e-accent-rgb')
      ).trim()
      if (next) accent = next
    }

    let width = 0
    let height = 0
    let cell = 16
    let columnGap = 16
    let columns = []
    const span = Math.max(0.06, Math.min(1, Number(density) || 1))

    const warmFrames = Math.max(0, Math.floor(prewarm))
    let warmed = false

    const makeColumn = (startAbove) => {
      const rows = height / cell
      let y = 0
      if (startAbove) {
        y = warmFrames > 0 ? (Math.random() * 1.4 - 0.5) * rows : -Math.random() * rows
      }
      return {
        y,
        speed: 0.35 + Math.random() * 0.55,
        glyph: pickGlyph(),
        swaps: 0,
      }
    }

    let head = ''
    let tail = ''
    const paint = () => {
      head = `rgba(${accent}, 0.95)`
      tail = `rgba(${accent}, 0.30)`
    }

    const step = () => {
      // Гасим старые глифы, не закрашивая холст чёрным.
      // Иначе дождь через пару секунд становится глухой чёрной плашкой
      // и прячет градиент под собой.
      ctx.globalCompositeOperation = 'destination-out'
      ctx.fillStyle = 'rgba(0, 0, 0, 0.16)'
      ctx.fillRect(0, 0, width, height)
      ctx.globalCompositeOperation = 'source-over'

      for (let i = 0; i < columns.length; i += 1) {
        const col = columns[i]
        const x = i * columnGap
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
      const full = Math.max(1, Math.ceil(width / cell))
      const count = Math.max(1, Math.round(full * span))
      columnGap = width / count
      const next = new Array(count)
      for (let i = 0; i < count; i += 1) next[i] = columns[i] || makeColumn(true)
      columns = next
      ctx.clearRect(0, 0, width, height)
      // Только при старте: при перетаскивании окна resize сыплется десятками.
      if (warmFrames > 0 && !warmed) {
        warmed = true
        paint()
        for (let n = 0; n < warmFrames; n += 1) step()
      }
    }

    readAccent(performance.now())
    resize()
    window.addEventListener('resize', resize)

    let raf = 0
    let last = -Infinity
    const frameMs = 1000 / Math.max(1, fps)
    // Допуск на дрожание vsync: без него на 60 Гц кадр через раз
    // «не дотягивает» до 33.3 мс, и дождь идёт рывками 20↔30 fps.
    const minGap = Math.max(0, frameMs - 4)

    const draw = (now) => {
      raf = window.requestAnimationFrame(draw)
      if (document.hidden) return
      if (now - last < minGap) return
      last = now
      readAccent(now)
      paint()
      step()
    }

    raf = window.requestAnimationFrame(draw)

    return () => {
      window.cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [paused, fps, prewarm, density])

  if (paused) return null

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
