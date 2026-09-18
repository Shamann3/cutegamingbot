import { useEffect, useRef, useState } from 'react'

// Плавная «накрутка» числа от предыдущего значения до value.
export default function CountUp({ value, duration = 900, className, signed = false }) {
  const [display, setDisplay] = useState(0)
  const fromRef = useRef(0)
  const rafRef = useRef(0)

  useEffect(() => {
    const target = Number(value) || 0
    const from = fromRef.current
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(target)
      fromRef.current = target
      return undefined
    }
    const start = performance.now()
    cancelAnimationFrame(rafRef.current)
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      const cur = Math.round(from + (target - from) * eased)
      setDisplay(cur)
      if (p < 1) rafRef.current = requestAnimationFrame(tick)
      else fromRef.current = target
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value, duration])

  const abs = Math.abs(display).toLocaleString('ru-RU')
  let text = display.toLocaleString('ru-RU')
  if (signed) {
    if (display > 0) text = `+${abs}`
    else if (display < 0) text = `−${abs}`
    else text = '0'
  }

  return <span className={className}>{text}</span>
}
