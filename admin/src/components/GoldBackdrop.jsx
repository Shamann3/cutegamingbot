import { useEffect, useRef } from 'react'

export default function GoldBackdrop({ lightMode = false }) {
  const canvasRef = useRef(null)
  const wrapRef  = useRef(null)

  useEffect(() => {
    if (lightMode) return

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf = 0
    let w = 0, h = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    function resize() {
      w = window.innerWidth
      h = window.innerHeight
      canvas.width  = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      canvas.style.width  = `${w}px`
      canvas.style.height = `${h}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)

    // Белые частицы (пыль)
    const count = Math.max(20, Math.min(40, Math.round(w / 28)))
    const particles = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: 0.4 + Math.random() * 1.2,
      speed: 3 + Math.random() * 10,
      sway: 4 + Math.random() * 12,
      phase: Math.random() * Math.PI * 2,
      twinkle: Math.random() * Math.PI * 2,
      tw: 0.5 + Math.random() * 1.2,
      base: 0.06 + Math.random() * 0.18,
    }))

    // Горизонтальные "скан-линии" (белые нити)
    const scanLines = Array.from({ length: 2 }, (_, i) => ({
      y: (h / 3) * (i + 1),
      amp: 12 + Math.random() * 20,
      len: 0.003 + Math.random() * 0.002,
      speed: 0.04 + Math.random() * 0.03,
      phase: Math.random() * Math.PI * 2,
      alpha: 0.025 + Math.random() * 0.025,
    }))

    let last = performance.now()
    let t = 0

    function frame(now) {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      t += dt
      ctx.clearRect(0, 0, w, h)

      // Рисуем координатную сетку (очень тёмная)
      ctx.strokeStyle = 'rgba(255,255,255,0.018)'
      ctx.lineWidth = 0.5
      const gridSize = 60
      for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
      }
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
      }

      // Скан-линии
      for (const sl of scanLines) {
        ctx.beginPath()
        for (let x = 0; x <= w; x += 10) {
          const y = sl.y + Math.sin(x * sl.len + t * sl.speed * 5 + sl.phase) * sl.amp
                  + Math.sin(t * 0.15 + sl.phase) * 20
          if (x === 0) ctx.moveTo(x, y)
          else         ctx.lineTo(x, y)
        }
        ctx.strokeStyle = `rgba(255,255,255,${sl.alpha})`
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      // Белые частицы
      for (const p of particles) {
        p.y      -= p.speed * dt
        p.x      += Math.sin(t * 0.5 + p.phase) * p.sway * dt
        p.twinkle += p.tw * dt
        if (p.y < -8) { p.y = h + 8; p.x = Math.random() * w }
        const a = p.base * (0.4 + 0.6 * (0.5 + 0.5 * Math.sin(p.twinkle)))
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255,255,255,${a})`
        ctx.fill()
      }

      raf = requestAnimationFrame(frame)
    }

    if (reduce) { frame(performance.now()); cancelAnimationFrame(raf) }
    else         { raf = requestAnimationFrame(frame) }

    // Параллакс
    let tx = 0, ty = 0, cx = 0, cy = 0, praf = 0
    const onMove = (e) => {
      tx = (e.clientX / w - 0.5) * 16
      ty = (e.clientY / h - 0.5) * 16
    }
    function parallax() {
      cx += (tx - cx) * 0.04
      cy += (ty - cy) * 0.04
      if (wrapRef.current) wrapRef.current.style.transform = `translate3d(${cx}px,${cy}px,0)`
      praf = requestAnimationFrame(parallax)
    }
    if (!reduce) {
      window.addEventListener('mousemove', onMove, { passive: true })
      praf = requestAnimationFrame(parallax)
    }

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(raf)
      cancelAnimationFrame(praf)
    }
  }, [lightMode])

  if (lightMode) {
    return (
      <div className="gold-bg gold-bg-light" aria-hidden="true">
        <div className="gold-bg-light-grad" />
      </div>
    )
  }

  return (
    <div className="gold-bg" aria-hidden="true">
      <div className="gold-bg-parallax" ref={wrapRef}>
        <div className="gold-fog gold-fog-1" />
        <div className="gold-fog gold-fog-2" />
        <canvas className="gold-particles" ref={canvasRef} />
      </div>
      <div className="gold-grain" />
    </div>
  )
}
