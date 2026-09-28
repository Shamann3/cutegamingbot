import { useEffect, useState } from 'react'

const STORAGE_KEY = 'cf_admin_perf'

function autoDetectLight() {
  // Цвет палитры остаётся и на телефоне. Монохром включается только кнопкой «Оптимизировать».
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
    setLightModeState(val)
    try { localStorage.setItem(STORAGE_KEY, val ? '1' : '0') } catch { /* ignore */ }
  }

  // Синхронизируем body-класс для CSS-переключения
  useEffect(() => {
    document.body.classList.toggle('perf-light', lightMode)
    return () => document.body.classList.remove('perf-light')
  }, [lightMode])

  return { lightMode, setLightMode }
}
