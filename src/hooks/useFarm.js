import { MAX_PLOTS } from '../types/farm'
import { useCallback, useEffect, useRef, useState } from 'react'
import * as farm from '../lib/farmClient'
import { mapFarmState } from '../lib/farmClient'
import { ApiError } from '../lib/apiClient'
import * as preview from '../lib/farmPreview'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useSettings } from '../context/SettingsContext'
import { useOnboardingOptional } from '../context/OnboardingContext'
import { PERF_MODES, PERF_POLL_MS } from '../constants/performance'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'
import { reportClientError } from '../lib/errorReporter'
import { useFarmToasts } from './useFarmToasts'
const IS_PREVIEW = import.meta.env.VITE_FARM_PREVIEW === 'true'

function isAuthApiError(error) {
  return error instanceof ApiError && error.code === 'auth'
}

function shouldPausePolling() {
  return typeof document !== 'undefined' && document.visibilityState === 'hidden'
}

const api = IS_PREVIEW
  ? {
      fetchFarmState: preview.previewFetchState,
      plantSeed: preview.previewPlant,
      waterPlot: preview.previewWater,
      installAutowater: preview.previewInstallAutowater,
      harvestPlot: preview.previewHarvest,
      clearPlot: preview.previewClear,
      buyPlot: preview.previewBuyPlot,
    }
  : farm

export function useFarm({ isActive = true } = {}) {
  const { performanceMode } = useSettings()
  const onboarding = useOnboardingOptional()
  const pollMs = PERF_POLL_MS[performanceMode]?.farm ?? PERF_POLL_MS[PERF_MODES.FULL].farm
  const { kut: sharedKut, inventoryTick, syncFromFarm } = usePlayerSync()
  const [plots, setPlots] = useState([])
  const [trees, setTrees] = useState(0)
  const [items, setItems] = useState({})
  const [itemsDisplay, setItemsDisplay] = useState(null)
  const [itemCatalog, setItemCatalog] = useState(null)
  const [farmItemIds, setFarmItemIds] = useState(null)
  const [seedCount, setSeedCount] = useState(0)
  const [tobaccoSeedCount, setTobaccoSeedCount] = useState(0)
  const [seedCounts, setSeedCounts] = useState({})
  const [farmCrops, setFarmCrops] = useState([])
  const [balanceBar, setBalanceBar] = useState([])
  const [axe, setAxe] = useState(null)
  const [waterCount, setWaterCount] = useState(0)
  const [autowaterCount, setAutowaterCount] = useState(0)
  const [kut, setKut] = useState(0)
  const [ownedPlots, setOwnedPlots] = useState(0)
  const [maxPlots, setMaxPlots] = useState(MAX_PLOTS)
  const [nextPlotId, setNextPlotId] = useState(null)
  const [nextPlotPrice, setNextPlotPrice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [seedEconomy, setSeedEconomy] = useState(null)
  const [actionMessage, setActionMessage] = useState(null)
  const msgTimerRef = useRef(null)
  const showMessage = (text) => {
    clearTimeout(msgTimerRef.current)
    setActionMessage(text)
    msgTimerRef.current = setTimeout(() => setActionMessage(null), 3500)
  }
  const [claimingDailySeed, setClaimingDailySeed] = useState(false)
  const busyRef = useRef(false)
  const pendingInventoryRefreshRef = useRef(false)
  const { gainToasts, spendToasts, processFarmNotify } = useFarmToasts()

  const setFarmError = useCallback((e) => {
    if (onboarding?.visible) return
    if (e instanceof ApiError) {
      setError(e.message)
      setErrorCode(e.code)
      return
    }
    setError(e?.message ?? 'Ошибка фермы')
    setErrorCode('api')
  }, [onboarding?.visible])

  const applyState = useCallback((apiState) => {
    const mapped = mapFarmState(apiState)
    setPlots(mapped.plots)
    setTrees(mapped.trees)
    setItems(mapped.items)
    setItemsDisplay(mapped.itemsDisplay)
    setItemCatalog(mapped.itemCatalog)
    setFarmItemIds(mapped.farmItemIds)
    setSeedCount(mapped.seedCount)
    setTobaccoSeedCount(mapped.tobaccoSeedCount)
    setSeedCounts(mapped.seedCounts ?? {})
    setFarmCrops(mapped.farmCrops ?? [])
    setBalanceBar(mapped.balanceBar ?? [])
    setAxe(mapped.axe ?? null)
    setWaterCount(mapped.waterCount ?? 0)
    setAutowaterCount(mapped.autowaterCount ?? 0)
    setKut(mapped.kut)
    setOwnedPlots(mapped.ownedPlots)
    setMaxPlots(mapped.maxPlots)
    setNextPlotId(mapped.nextPlotId)
    setNextPlotPrice(mapped.nextPlotPrice)
    setSeedEconomy(mapped.seedEconomy ?? null)
    syncFromFarm(mapped.kut)
    onboarding?.syncFarmOnboarding?.(mapped.onboarding)
    setError(null)
    setErrorCode(null)
  }, [syncFromFarm, onboarding?.syncFarmOnboarding])

  const refresh = useCallback(async () => {
    const data = await api.fetchFarmState()
    applyState(data)
    return data
  }, [applyState])

  useEffect(() => {
    let cancelled = false
    let intervalId = null

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    const handlePollError = (error) => {
      if (cancelled || onboarding?.visible) return
      if (isAuthApiError(error)) {
        stopPolling()
        setFarmError(error)
        return
      }
      setFarmError(error)
      reportClientError({
        code: 'ERR_FARM_POLL',
        message: error?.message ?? '',
        path: '/api/farm/state',
        context: 'poll',
      })
    }

    const poll = () => {
      if (busyRef.current || !isActive || onboarding?.visible || shouldPausePolling()) return
      refresh().catch(handlePollError)
    }

    if (!IS_PREVIEW && !canAuthenticate()) {
      setError(getAuthErrorMessage())
      setLoading(false)
      return undefined
    }

    if (!isActive) {
      return undefined
    }

    refresh()
      .catch((e) => !cancelled && setFarmError(e))
      .finally(() => !cancelled && setLoading(false))

    intervalId = window.setInterval(poll, pollMs)

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        poll()
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      cancelled = true
      stopPolling()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [isActive, pollMs, refresh, onboarding?.visible, setFarmError])

  useEffect(() => {
    if (!onboarding?.farmRefreshNonce) return undefined
    refresh().catch(() => {})
    return undefined
  }, [onboarding?.farmRefreshNonce, refresh])

  useEffect(() => {
    if (!onboarding?.visible) return undefined
    setError(null)
    setErrorCode(null)
    return undefined
  }, [onboarding?.visible])

  useEffect(() => {
    if (inventoryTick === 0) return undefined
    if (busyRef.current) {
      pendingInventoryRefreshRef.current = true
      return undefined
    }
    refresh().catch(() => {})
    return undefined
  }, [inventoryTick, refresh])

  useEffect(() => {
    const onBought = () => {
      if (busyRef.current) {
        pendingInventoryRefreshRef.current = true
        return
      }
      refresh().catch(() => {})
    }
    window.addEventListener('farm:purchase-complete', onBought)
    return () => window.removeEventListener('farm:purchase-complete', onBought)
  }, [refresh])

  const runAction = useCallback(
    async (apiFn, ...args) => {
      busyRef.current = true
      setError(null)
      setErrorCode(null)
      try {
        const data = await apiFn(...args)
        applyState(data)
        processFarmNotify(data)
        return data
      } catch (e) {
        setFarmError(e)
        throw e
      } finally {
        busyRef.current = false
        if (pendingInventoryRefreshRef.current) {
          pendingInventoryRefreshRef.current = false
          refresh().catch(() => {})
        }
      }
    },
    [applyState, setFarmError, processFarmNotify, refresh],
  )

  const claimDailySeed = useCallback(async (seedItemId) => {
    if (IS_PREVIEW) return undefined
    setClaimingDailySeed(true)
    setError(null)
    setErrorCode(null)
    try {
      const data = await farm.claimDailySeed(seedItemId)
      applyState(data)
      processFarmNotify(data)
      const reward = data.dailySeedReward
      if (reward?.label) {
        showMessage(`🎁 Получено: ${reward.label}`)
      }
      return data
    } catch (e) {
      setFarmError(e)
      throw e
    } finally {
      setClaimingDailySeed(false)
    }
  }, [applyState, setFarmError, processFarmNotify])

  const actions = {
    plant: (plotId, seedItemId) => runAction(api.plantSeed, plotId, seedItemId),
    water: (plotId, waterItemId) => runAction(api.waterPlot, plotId, waterItemId),
    autowater: (plotId) => runAction(api.installAutowater, plotId),
    harvest: (plotId) => runAction(api.harvestPlot, plotId),
    clear: (plotId) => runAction(api.clearPlot, plotId),
    buyPlot: () => runAction(api.buyPlot),
  }

  return {
    plots,
    trees,
    items,
    itemsDisplay,
    itemCatalog,
    farmItemIds,
    seedCount,
    tobaccoSeedCount,
    seedCounts,
    farmCrops,
    balanceBar,
    axe,
    waterCount,
    autowaterCount,
    kut: sharedKut ?? kut,
    ownedPlots,
    maxPlots,
    nextPlotId,
    nextPlotPrice,
    loading,
    error,
    errorCode,
    actionMessage,
    gainToasts,
    spendToasts,
    seedEconomy,
    claimingDailySeed,
    claimDailySeed,
    actions,
    isPreview: IS_PREVIEW,
  }
}
