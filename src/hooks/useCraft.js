import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { executeCraft, fetchCraftRecipes } from '../lib/craftClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'
import { reportClientError } from '../lib/errorReporter'

const TOAST_MS = 3200

function formatCraftError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка крафта'
}

export function useCraft({ isActive = true } = {}) {
  const { kut: sharedKut, syncFromCraft } = usePlayerSync()
  const [kut, setKut] = useState(0)
  const [recipes, setRecipes] = useState([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [craftingPairKey, setCraftingPairKey] = useState(null)
  const [craftMessage, setCraftMessage] = useState(null)
  const busyRef = useRef(false)
  const toastTimeoutRef = useRef(null)
  const mountedRef = useRef(false)

  const displayKut = sharedKut ?? kut

  const applyPayload = useCallback((data, { syncPlayer = true } = {}) => {
    setKut(data.kut ?? 0)
    setRecipes(data.recipes ?? [])
    setError(null)
    setErrorCode(null)
    if (syncPlayer) {
      syncFromCraft(data)
    }
  }, [syncFromCraft])

  const showCraftMessage = useCallback((message) => {
    if (!message) return
    setCraftMessage(message)
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => {
      setCraftMessage(null)
    }, TOAST_MS)
  }, [])

  const loadRecipes = useCallback(async ({ silent = false } = {}) => {
    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return
    }

    if (!silent) {
      if (!mountedRef.current) {
        setInitialLoading(true)
      } else {
        setRefreshing(true)
      }
    }

    try {
      const data = await fetchCraftRecipes()
      if (!mountedRef.current) return
      applyPayload(data)
    } catch (err) {
      if (!mountedRef.current) return
      const message = formatCraftError(err)
      setError(message)
      setErrorCode(err instanceof ApiError ? err.code : 'error')
      if (!(err instanceof ApiError)) {
        reportClientError({
          code: 'ERR_CRAFT_LOAD',
          message,
          path: '/api/craft/recipes',
          context: 'load',
        })
      }
    } finally {
      if (mountedRef.current) {
        setInitialLoading(false)
        setRefreshing(false)
      }
    }
  }, [applyPayload])

  const craftRecipe = useCallback(async (slotA, slotB) => {
    if (busyRef.current) return null
    busyRef.current = true
    setCraftingPairKey(`${slotA}|${slotB}`)
    setError(null)
    setErrorCode(null)

    try {
      const data = await executeCraft(slotA, slotB)
      applyPayload(data)
      showCraftMessage(data.message ?? (data.craftSuccess ? 'Крафт успешен!' : 'Крафт не удался'))
      return data
    } catch (err) {
      const message = formatCraftError(err)
      setError(message)
      setErrorCode(err instanceof ApiError ? err.code : 'error')
      if (!(err instanceof ApiError)) {
        reportClientError({
          code: 'ERR_CRAFT_EXECUTE',
          message,
          path: '/api/craft/execute',
          context: 'execute',
        })
      }
      throw err
    } finally {
      busyRef.current = false
      setCraftingPairKey(null)
    }
  }, [applyPayload, showCraftMessage])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (toastTimeoutRef.current) {
        window.clearTimeout(toastTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!isActive) return undefined
    loadRecipes()
    return undefined
  }, [isActive, loadRecipes])

  return {
    kut: displayKut,
    recipes,
    initialLoading,
    refreshing,
    error,
    errorCode,
    craftingPairKey,
    craftMessage,
    loadRecipes,
    craftRecipe,
  }
}
