import { useEffect } from 'react'

/** Свайп вправо открывает список вкладок, влево закрывает.
 *  Жест должен быть явно горизонтальным, чтобы не спорить с прокруткой. */
export default function useDrawerSwipe({ enabled, open, onOpen, onClose }) {
  useEffect(() => {
    if (!enabled) return undefined
    let startX = 0
    let startY = 0
    let tracking = false

    const onStart = (event) => {
      if (event.touches.length !== 1) return
      const target = event.target
      if (target instanceof Element && target.closest('input, textarea, select, [data-swipe-ignore]')) return
      startX = event.touches[0].clientX
      startY = event.touches[0].clientY
      tracking = true
    }

    const onEnd = (event) => {
      if (!tracking) return
      tracking = false
      const touch = event.changedTouches[0]
      if (!touch) return
      const dx = touch.clientX - startX
      const dy = touch.clientY - startY
      if (Math.abs(dx) < 64 || Math.abs(dx) < Math.abs(dy) * 1.25) return
      if (!open && dx > 0) onOpen()
      if (open && dx < 0) onClose()
    }

    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchend', onEnd, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onStart)
      window.removeEventListener('touchend', onEnd)
    }
  }, [enabled, open, onOpen, onClose])
}
