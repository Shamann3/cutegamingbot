import { useEffect, useRef } from 'react'

export default function CursorGlow() {
  const glowRef = useRef(null)

  useEffect(() => {
    const glow = glowRef.current
    if (!glow) return

    let tx = -400, ty = -400
    let cx = -400, cy = -400
    let rafId = null

    const animate = () => {
      cx += (tx - cx) * 0.09
      cy += (ty - cy) * 0.09
      glow.style.transform = `translate(${cx}px, ${cy}px)`

      if (Math.abs(tx - cx) > 0.3 || Math.abs(ty - cy) > 0.3) {
        rafId = requestAnimationFrame(animate)
      } else {
        rafId = null
      }
    }

    const onMove = (e) => {
      tx = e.clientX
      ty = e.clientY
      if (!rafId) rafId = requestAnimationFrame(animate)
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    return () => {
      window.removeEventListener('mousemove', onMove)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  return <div ref={glowRef} className="cursor-glow" aria-hidden="true" />
}
