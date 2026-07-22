import { useEffect, useState } from 'react'

// Единый секундный тикер на все карточки розыгрышей: один setInterval на всё
// приложение, компоненты подписываются и ре-рендерятся раз в секунду. Дешевле
// и предсказуемее, чем собственный interval в каждой карточке.
const listeners = new Set()
let timer = null

function ensureTimer() {
  if (timer != null) return
  timer = window.setInterval(() => {
    const value = Date.now()
    listeners.forEach((fn) => fn(value))
  }, 1000)
}

export function useNow(active = true) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return undefined
    listeners.add(setNow)
    ensureTimer()
    return () => {
      listeners.delete(setNow)
      if (listeners.size === 0 && timer != null) {
        window.clearInterval(timer)
        timer = null
      }
    }
  }, [active])
  return now
}
