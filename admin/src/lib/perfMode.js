import { useEffect, useState } from 'react'

const STORAGE_KEY = 'cf_admin_perf'
const listeners = new Set()

function autoDetectLight() {
  // Цвет палитры не гасим. Кнопка только режет тяжёлые эффекты и дождь символов.
  return false
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
    const next = Boolean(val)
    setLightModeState(next)
    try { localStorage.setItem(STORAGE_KEY, next ? '1' : '0') } catch { /* ignore */ }
    listeners.forEach((fn) => fn(next))
  }

  useEffect(() => {
    const sync = (next) => setLightModeState(Boolean(next))
    listeners.add(sync)
    return () => listeners.delete(sync)
  }, [])

  // Синхронизируем body-класс для CSS-переключения
  useEffect(() => {
    document.body.classList.toggle('perf-light', lightMode)
    return () => {
      if (listeners.size <= 1) document.body.classList.remove('perf-light')
    }
  }, [lightMode])

  return { lightMode, setLightMode }
}
