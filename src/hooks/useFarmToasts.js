import { useCallback, useEffect, useRef, useState } from 'react'

const TOAST_TTL_MS = 3200

export function useFarmToasts() {
  const [gainToasts, setGainToasts] = useState([])
  const [spendToasts, setSpendToasts] = useState([])
  const timersRef = useRef(new Map())

  useEffect(() => () => {
    timersRef.current.forEach((timer) => clearTimeout(timer))
    timersRef.current.clear()
  }, [])

  const pushToasts = useCallback((kind, items) => {
    if (!items?.length) return
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const entry = { id, items }
    const setter = kind === 'gain' ? setGainToasts : setSpendToasts
    setter((prev) => [...prev, entry])
    const timer = setTimeout(() => {
      setter((prev) => prev.filter((row) => row.id !== id))
      timersRef.current.delete(id)
    }, TOAST_TTL_MS)
    timersRef.current.set(id, timer)
  }, [])

  const processFarmNotify = useCallback((data) => {
    pushToasts('gain', data?.farmGained)
    pushToasts('spend', data?.farmSpent)
  }, [pushToasts])

  return { gainToasts, spendToasts, processFarmNotify }
}
