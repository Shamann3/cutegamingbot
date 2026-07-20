import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchGiveawayWinnersFeed } from '../lib/giveawaysClient'

const REFRESH_MS = 60000

export function useGiveawayWinnersFeed() {
  const [winners, setWinners] = useState([])
  const mountedRef = useRef(false)

  const load = useCallback(async () => {
    try {
      const data = await fetchGiveawayWinnersFeed()
      if (mountedRef.current) setWinners(data?.winners ?? [])
    } catch {
      // Лента — необязательный декоративный элемент, не должна ронять модуль
      // ошибкой загрузки; при сбое просто остаётся пустой/старой.
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => {
      mountedRef.current = false
      window.clearInterval(timer)
    }
  }, [load])

  return { winners }
}
