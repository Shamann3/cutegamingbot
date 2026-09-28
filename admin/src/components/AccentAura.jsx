import { useState } from 'react'
import MatrixRain from './MatrixRain'

function deviceIsCalm() {
  if (typeof window === 'undefined') return true
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

/**
 * Фон панелей: мягкий градиент выбранного цвета сверху
 * и редкий дождь символов в верхней полосе. На слабых
 * устройствах остаётся только градиент — он ничего не считает.
 */
export default function AccentAura() {
  const [calm] = useState(deviceIsCalm)
  return (
    <div className="accent-aura" aria-hidden="true">
      <div className="accent-aura-wash" />
      {calm ? null : (
        <div className="accent-aura-slot">
          <MatrixRain className="accent-aura-rain" fps={18} prewarm={6} />
        </div>
      )}
    </div>
  )
}
