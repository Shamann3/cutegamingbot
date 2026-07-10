import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { fetchInventory, mapInventoryState } from '../lib/inventoryClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useSettings } from '../context/SettingsContext'
import { PERF_MODES, PERF_POLL_MS } from '../constants/performance'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'

function formatError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка рюкзака'
}

export function useInventory({ isActive = true } = {}) {
  const { performanceMode } = useSettings()
  const pollMs = PERF_POLL_MS[performanceMode]?.farm ?? PERF_POLL_MS[PERF_MODES.FULL].farm
  const { kut: sharedKut, inventoryTick } = usePlayerSync()

  const [kut, setKut] = useState(0)
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState({ totalKinds: 0, totalCount: 0, groups: {} })
  const [axe, setAxe] = useState(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)

  const mountedRef = useRef(false)

  const applyState = useCallback((data) => {
    const mapped = mapInventoryState(data)
    setKut(mapped.kut)
    setItems(mapped.items)
    setSummary(mapped.summary)
    setAxe(mapped.axe)
    setError(null)
    setErrorCode(null)
  }, [])

  const loadInventory = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setRefreshing(true)
    try {
      const data = await fetchInventory()
      applyState(data)
      return data
    } catch (e) {
      setError(formatError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [applyState])

  const displayKut = sharedKut ?? kut

  useEffect(() => {
    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return undefined
    }
    if (!isActive) return undefined

    const isFirst = !mountedRef.current
    mountedRef.current = true
    if (isFirst) setInitialLoading(true)

    loadInventory({ silent: !isFirst })
      .catch(() => {})
      .finally(() => setInitialLoading(false))

    return undefined
  }, [isActive, loadInventory])

  useEffect(() => {
    if (!isActive || !canAuthenticate() || inventoryTick === 0) return undefined
    loadInventory({ silent: true }).catch(() => {})
    return undefined
  }, [inventoryTick, isActive, loadInventory])

  useEffect(() => {
    if (!isActive || !canAuthenticate()) return undefined
    let intervalId = null
    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }
    const poll = () => {
      if (initialLoading) return
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      loadInventory({ silent: true }).catch((err) => {
        if (err instanceof ApiError && err.code === 'auth') stopPolling()
      })
    }
    intervalId = window.setInterval(poll, pollMs)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') poll()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [initialLoading, isActive, pollMs, loadInventory])

  return {
    kut: displayKut,
    items,
    summary,
    axe,
    initialLoading,
    refreshing,
    error,
    errorCode,
    reload: loadInventory,
  }
}
