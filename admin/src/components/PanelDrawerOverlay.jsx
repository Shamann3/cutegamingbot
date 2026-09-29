import { useEffect, useRef, useState } from 'react'

/**
 * Затемнение под сайдбаром. Клики сквозь него: закрытие слушает сама панель,
 * иначе этот слой забирает нажатия у кнопок.
 */
export default function PanelDrawerOverlay({ open, onClose, ms = 280 }) {
  const [mounted, setMounted] = useState(open)
  const [shown, setShown] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (open) {
      setMounted(true)
      const id = window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => setShown(true))
      })
      return () => window.cancelAnimationFrame(id)
    }
    setShown(false)
    const t = window.setTimeout(() => setMounted(false), ms)
    return () => window.clearTimeout(t)
  }, [open, ms])

  useEffect(() => {
    const node = ref.current
    if (!node) return undefined
    node.style.setProperty('pointer-events', 'none', 'important')
    return undefined
  }, [mounted, shown])

  if (!mounted) return null

  return (
    <div
      ref={ref}
      className={`panel-mobile-overlay${shown ? ' is-shown' : ''}`}
      aria-hidden="true"
      onClick={onClose}
    />
  )
}
