import { useEffect, useRef } from 'react'

const GLYPHS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ΣΔΛΞΨΩ<>/{}[]=+*#$'
const FONT_SIZE = 15

/**
 * Матричный «дождь кода» на фоне.
 * Один canvas, ограниченный fps, пауза во вкладке в фоне.
 * Цвет берётся из акцента палитры.
 */
export default function MatrixRain({
  paused = false,
  className = 'ent-matrix',
  fps = 24,
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (paused) return undefined
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return undefined

    const root = document.documentElement
    const accentRgb =
      getComputedStyle(root).getPropertyValue('--e-accent-rgb').trim() || '255, 5, 36'

    let width = 0
    let height = 0
    let columns = 0
    let drops = []

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth || window.innerWidth
      height = canvas.clientHeight || window.innerHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.font = `${FONT_SIZE}px "SFMono-Regular", "JetBrains Mono", Menlo, monospace`
      ctx.textBaseline = 'top'
      const nextColumns = Math.max(1, Math.floor(width / FONT_SIZE))
      drops = Array.from({ length: nextColumns }, (_, i) => (
        drops[i] != null ? drops[i] : -Math.random() * (height / FONT_SIZE)
      ))
      columns = nextColumns
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

      ctx.fillStyle = 'rgba(0, 0, 0, 0.10)'
      ctx.fillRect(0, 0, width, height)

      for (let i = 0; i < columns; i += 1) {
        const x = i * FONT_SIZE
        const y = drops[i] * FONT_SIZE

        ctx.fillStyle = `rgba(${accentRgb}, 0.92)`
        ctx.fillText(GLYPHS[(Math.random() * GLYPHS.length) | 0], x, y)
        ctx.fillStyle = `rgba(${accentRgb}, 0.22)`
        ctx.fillText(GLYPHS[(Math.random() * GLYPHS.length) | 0], x, y - FONT_SIZE)

        if (y > height && Math.random() > 0.975) drops[i] = 0
        else drops[i] += 1
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
