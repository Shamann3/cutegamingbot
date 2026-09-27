import { useEffect, useState } from 'react'

/**
 * Backdrop для drawer: закрытие по клику + плавный fade in/out.
 * Держит DOM на время анимации выхода, чтобы не было резкого исчезновения.
 */
export default function PanelDrawerOverlay({ open, onClose, ms = 280 }) {
  const [mounted, setMounted] = useState(open)
  const [shown, setShown] = useState(false)

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

  if (!mounted) return null

  return (
    <button
      type="button"
      className={`panel-mobile-overlay${shown ? ' is-shown' : ''}`}
      aria-label="Закрыть меню"
      onClick={onClose}
    />
  )
}
