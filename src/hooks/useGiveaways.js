import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { fetchGiveaways, participateInGiveaway } from '../lib/giveawaysClient'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'

const ACTIVE_SYNC_MS = 30000

function formatGiveawayError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка розыгрышей'
}

export function useGiveaways({ isActive = true } = {}) {
  const [giveaways, setGiveaways] = useState([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [participatingId, setParticipatingId] = useState(null)
  const mountedRef = useRef(false)
  const busyRef = useRef(false)

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return
    }
    if (!silent) {
      if (!mountedRef.current) setInitialLoading(true)
      else setRefreshing(true)
    }
    try {
      const data = await fetchGiveaways()
      if (!mountedRef.current) return
      setGiveaways(data?.giveaways ?? [])
      setError(null)
      setErrorCode(null)
    } catch (err) {
      if (!mountedRef.current) return
      setError(formatGiveawayError(err))
      setErrorCode(err instanceof ApiError ? err.code : 'error')
    } finally {
      if (mountedRef.current) {
        setInitialLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  const participate = useCallback(async (giveawayId) => {
    if (busyRef.current || !giveawayId) return
    busyRef.current = true
    setParticipatingId(giveawayId)
    try {
      await participateInGiveaway(giveawayId)
      await load({ silent: true })
      return true
    } catch (err) {
      setError(formatGiveawayError(err))
      return false
    } finally {
      busyRef.current = false
      setParticipatingId(null)
    }
  }, [load])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (!isActive) return undefined
    load({ silent: mountedRef.current })
    const timer = window.setInterval(() => load({ silent: true }), ACTIVE_SYNC_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') load({ silent: true })
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [isActive, load])

  return {
    giveaways,
    initialLoading,
    refreshing,
    error,
    errorCode,
    participatingId,
    participate,
    reload: () => load({ silent: true }),
  }
}
