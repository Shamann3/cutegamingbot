import { useCallback, useState } from 'react'
import { fetchGiveawayHistory } from '../lib/giveawaysClient'

export function useGiveawayHistory() {
  const [giveaways, setGiveaways] = useState(null) // null = ещё не грузили
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGiveawayHistory()
      setGiveaways(data?.giveaways ?? [])
      setError(null)
    } catch (err) {
      setError(err?.message ?? 'Ошибка загрузки истории')
    } finally {
      setLoading(false)
    }
  }, [])

  return { giveaways, loading, error, load }
}
