import { useCallback, useEffect, useState } from 'react'
import { fetchChestState, openChests, fetchDropFeed } from '../lib/chestClient'

export function useChests(isActive) {
  const [state, setState] = useState(null)
  const [feed, setFeed] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [loadedOnce, setLoadedOnce] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchChestState()
      setState(data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
      setLoadedOnce(true)
    }
  }, [])

  const refreshFeed = useCallback(async () => {
    try { setFeed(await fetchDropFeed()) } catch { /* feed is best-effort */ }
  }, [])

  useEffect(() => {
    if (isActive && !loadedOnce) {
      refresh()
      refreshFeed()
    }
  }, [isActive, loadedOnce, refresh, refreshFeed])

  useEffect(() => {
    if (!isActive) return undefined
    const id = setInterval(() => { refreshFeed() }, 12000)
    return () => clearInterval(id)
  }, [isActive, refreshFeed])

  const open = useCallback(async (count) => {
    const res = await openChests(count)
    setState((prev) => (prev ? { ...prev, keys: res.keys, shards: res.shards } : prev))
    return res
  }, [])

  return { state, feed, loading, error, refresh, refreshFeed, open }
}
