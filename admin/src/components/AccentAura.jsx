import { useState } from 'react'
import MatrixRain from './MatrixRain'
import { usePerfMode } from '../lib/perfMode'

function deviceIsStill() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

/**
 * Фон панелей: градиент выбранного цвета и редкий дождь символов сверху.
 * В режиме оптимизации дождь остаётся, но колонок почти нет.
 * На слабом железе и при «уменьшить движение» остаётся только градиент.
 */
export default function AccentAura() {
  const { lightMode } = usePerfMode()
  const [still] = useState(deviceIsStill)
  const sparse = lightMode || still
  return (
    <div className="accent-aura" aria-hidden="true">
      <div className="accent-aura-wash" />
      {still ? null : (
        <div className="accent-aura-slot">
          <MatrixRain
            className="accent-aura-rain"
            density={sparse ? 0.1 : 1}
            fps={sparse ? 10 : 18}
            prewarm={sparse ? 2 : 6}
          />
        </div>
      )}
    </div>
  )
}
