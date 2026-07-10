import { useEffect, useRef } from 'react'

const SWIPE_THRESHOLD = 56
const TAB_ORDER = ['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'settings']

function nextTab(tab) {
  const index = TAB_ORDER.indexOf(tab)
  if (index < 0 || index >= TAB_ORDER.length - 1) return null
  return TAB_ORDER[index + 1]
}

function prevTab(tab) {
  const index = TAB_ORDER.indexOf(tab)
  if (index <= 0) return null
  return TAB_ORDER[index - 1]
}

export function useSwipeTabs({ activeTab, onChange, enabled = true }) {
  const touchRef = useRef({ startX: 0, startY: 0, tracking: false })

  useEffect(() => {
    if (!enabled) return undefined

    const onTouchStart = (event) => {
      const touch = event.touches[0]
      touchRef.current = {
        startX: touch.clientX,
        startY: touch.clientY,
        tracking: true,
      }
    }

    const onTouchEnd = (event) => {
      if (!touchRef.current.tracking) return
      const touch = event.changedTouches[0]
      const dx = touch.clientX - touchRef.current.startX
      const dy = touch.clientY - touchRef.current.startY
      touchRef.current.tracking = false

      if (Math.abs(dx) < SWIPE_THRESHOLD) return
      if (Math.abs(dy) > Math.abs(dx)) return

      if (dx < 0) {
        const next = nextTab(activeTab)
        if (next) onChange(next)
      } else if (dx > 0) {
        const prev = prevTab(activeTab)
        if (prev) onChange(prev)
      }
    }

    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchend', onTouchEnd, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [activeTab, enabled, onChange])
}
