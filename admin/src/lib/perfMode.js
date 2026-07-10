import { useEffect, useState } from 'react'

const STORAGE_KEY = 'cf_admin_perf'

function autoDetectLight() {
  if (typeof window === 'undefined') return false
  const isMobile = /iPhone|iPad|Android|Mobile/i.test(navigator.userAgent)
  const isSmallScreen = window.innerWidth <= 1024
  const isWeak = (navigator.hardwareConcurrency || 4) <= 4
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  return isMobile || isSmallScreen || isWeak || prefersReduced
}

export function usePerfMode() {
  const [lightMode, setLightModeState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored !== null) return stored === '1'
    } catch { /* ignore */ }
    return autoDetectLight()
  })

  const setLightMode = (val) => {
    setLightModeState(val)
    try { localStorage.setItem(STORAGE_KEY, val ? '1' : '0') } catch { /* ignore */ }
  }

  // Синхронизируем body-класс для CSS-переключения
  useEffect(() => {
    document.body.classList.toggle('perf-light', lightMode)
    return () => document.body.classList.remove('perf-light')
  }, [lightMode])

  // Следим за изменением системной настройки prefers-reduced-motion
  useEffect(() => {
    const mql = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!mql) return
    const onChange = (e) => {
      if (e.matches) setLightModeState(true)
    }
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])

  return { lightMode, setLightMode }
}
