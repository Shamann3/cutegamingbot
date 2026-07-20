import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchGiveawayHistory } from '../lib/giveawaysClient'

export function useGiveawayHistory() {
  const [giveaways, setGiveaways] = useState(null) // null = ещё не грузили
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const mountedRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGiveawayHistory()
      if (mountedRef.current) {
        setGiveaways(data?.giveaways ?? [])
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err?.message ?? 'Ошибка загрузки истории')
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  return { giveaways, loading, error, load }
}
