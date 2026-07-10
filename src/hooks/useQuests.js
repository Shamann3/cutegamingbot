import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import {
  acceptQuest as acceptQuestApi,
  cancelQuest as cancelQuestApi,
  claimDailySeed as claimDailySeedApi,
  claimQuestReward,
  fetchQuestsState,
  mapQuestsState,
} from '../lib/questClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'
import { reportClientError } from '../lib/errorReporter'

const TOAST_MS = 3400
const BADGE_POLL_MS = 45000
const ACTIVE_SYNC_MS = 30000

function formatQuestError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка заданий'
}

function confirmQuestCancel(message) {
  const tg = window.Telegram?.WebApp
  if (typeof tg?.showConfirm === 'function') {
    return new Promise((resolve) => {
      let settled = false
      const settle = (confirmed) => {
        if (settled) return
        settled = true
        resolve(Boolean(confirmed))
      }
      try {
        const result = tg.showConfirm(message, settle)
        if (typeof result?.then === 'function') {
          result.then(settle).catch(() => settle(window.confirm(message)))
        } else if (typeof result === 'boolean') {
          settle(result)
        }
      } catch {
        settle(window.confirm(message))
      }
    })
  }
  return Promise.resolve(window.confirm(message))
}

export function useQuests({ isActive = true, badgeOnly = false } = {}) {
  const { kut: sharedKut, syncFromFarm } = usePlayerSync()
  const [kut, setKut] = useState(0)
  const [sections, setSections] = useState({ hourly: [], daily: [], weekly: [], events: [] })
  const [readyCount, setReadyCount] = useState(0)
  const [npcName, setNpcName] = useState('Задания')
  const [npcEmoji, setNpcEmoji] = useState('📜')
  const [periodLabels, setPeriodLabels] = useState({})
  const [periodTimers, setPeriodTimers] = useState({})
  const [acceptRules, setAcceptRules] = useState({ hourly: 1, daily: 1, weekly: 1 })
  const [seedEconomy, setSeedEconomy] = useState(null)
  const [farmCrops, setFarmCrops] = useState([])
  const [initialLoading, setInitialLoading] = useState(!badgeOnly)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [claimingQuestId, setClaimingQuestId] = useState(null)
  const [acceptingQuestId, setAcceptingQuestId] = useState(null)
  const [cancelingQuestId, setCancelingQuestId] = useState(null)
  const [claimingDailySeed, setClaimingDailySeed] = useState(false)
  const [questMessage, setQuestMessage] = useState(null)
  const busyRef = useRef(false)
  const toastTimeoutRef = useRef(null)
  const mountedRef = useRef(false)

  const displayKut = sharedKut ?? kut

  const showQuestMessage = useCallback((message) => {
    if (!message) return
    setQuestMessage(message)
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => {
      setQuestMessage(null)
    }, TOAST_MS)
  }, [])

  const applyPayload = useCallback((data, { syncPlayer = true } = {}) => {
    const mapped = mapQuestsState(data)
    if (import.meta.env.DEV) {
      const accepted = Object.values(mapped.sections ?? {}).flat().filter((q) => q.accepted)
      if (accepted.length) {
        // eslint-disable-next-line no-console
        console.warn('[quests] active:', accepted.map((q) => `${q.id} timer=${q.timerRemainingSec}`))
      }
    }
    setKut(mapped.kut)
    setSections(mapped.sections)
    setReadyCount(mapped.readyCount)
    setNpcName(mapped.npcName)
    setNpcEmoji(mapped.npcEmoji)
    setPeriodLabels(mapped.periodLabels)
    setPeriodTimers(mapped.periodTimers)
    setAcceptRules(mapped.acceptRules)
    setSeedEconomy(mapped.seedEconomy)
    setFarmCrops(mapped.farmCrops)
    setError(null)
    setErrorCode(null)
    if (syncPlayer && mapped.kut != null) {
      syncFromFarm(mapped.kut)
    }
    if (mapped.questReward) {
      const labels = (mapped.questReward.rewards ?? []).map((item) => item.label).filter(Boolean)
      const title = mapped.questReward.title ?? 'Награда'
      showQuestMessage(labels.length ? `${title}: ${labels.join(', ')}` : `${title} получена!`)
    }
    if (data?.dailySeedReward?.label) {
      showQuestMessage(`Получено: ${data.dailySeedReward.label}`)
    }
    return mapped
  }, [showQuestMessage, syncFromFarm])

  const loadQuests = useCallback(async ({ silent = false } = {}) => {
    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return null
    }

    if (!silent) {
      if (!mountedRef.current) {
        setInitialLoading(true)
      } else {
        setRefreshing(true)
      }
    }

    try {
      const data = await fetchQuestsState()
      if (!mountedRef.current) return null
      return applyPayload(data)
    } catch (err) {
      if (!mountedRef.current) return null
      const message = formatQuestError(err)
      setError(message)
      setErrorCode(err instanceof ApiError ? err.code : 'error')
      if (!(err instanceof ApiError)) {
        reportClientError({
          code: 'ERR_QUESTS_LOAD',
          message,
          path: '/api/quests/state',
          context: 'load',
        })
      }
      return null
    } finally {
      if (mountedRef.current) {
        setInitialLoading(false)
        setRefreshing(false)
      }
    }
  }, [applyPayload])

  const claimQuest = useCallback(async (questId) => {
    if (busyRef.current || !questId) return
    busyRef.current = true
    setClaimingQuestId(questId)
    try {
      const data = await claimQuestReward(questId)
      applyPayload(data)
    } catch (err) {
      showQuestMessage(formatQuestError(err))
    } finally {
      busyRef.current = false
      setClaimingQuestId(null)
    }
  }, [applyPayload, showQuestMessage])

  const acceptQuest = useCallback(async (questId) => {
    if (busyRef.current || !questId) return
    busyRef.current = true
    setAcceptingQuestId(questId)
    try {
      const data = await acceptQuestApi(questId)
      applyPayload(data)
      showQuestMessage('Задание взято. Выполняй на ферме')
    } catch (err) {
      showQuestMessage(formatQuestError(err))
    } finally {
      busyRef.current = false
      setAcceptingQuestId(null)
    }
  }, [applyPayload, showQuestMessage])

  const cancelQuest = useCallback(async (questId) => {
    if (busyRef.current || !questId) return
    const confirmed = await confirmQuestCancel(
      'Отменить задание? Весь прогресс по нему не сохранится.',
    )
    if (!confirmed) return

    busyRef.current = true
    setCancelingQuestId(questId)
    try {
      const data = await cancelQuestApi(questId)
      applyPayload(data)
      showQuestMessage('Задание отменено')
    } catch (err) {
      showQuestMessage(formatQuestError(err))
    } finally {
      busyRef.current = false
      setCancelingQuestId(null)
    }
  }, [applyPayload, showQuestMessage])

  const claimDailySeed = useCallback(async (seedItemId) => {
    if (busyRef.current) return
    busyRef.current = true
    setClaimingDailySeed(true)
    try {
      const farmData = await claimDailySeedApi(seedItemId)
      const data = await fetchQuestsState()
      applyPayload(data, { syncPlayer: false })
      if (farmData?.kut != null) {
        syncFromFarm(farmData.kut)
      }
      if (farmData?.dailySeedReward?.label) {
        showQuestMessage(`Получено: ${farmData.dailySeedReward.label}`)
      }
    } catch (err) {
      showQuestMessage(formatQuestError(err))
    } finally {
      busyRef.current = false
      setClaimingDailySeed(false)
    }
  }, [applyPayload, showQuestMessage, syncFromFarm])

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
    if (!isActive && !badgeOnly) return undefined
    loadQuests({ silent: mountedRef.current })
    if (!isActive && badgeOnly) {
      const timer = window.setInterval(() => {
        loadQuests({ silent: true })
      }, BADGE_POLL_MS)
      return () => window.clearInterval(timer)
    }
    if (isActive && !badgeOnly) {
      const timer = window.setInterval(() => {
        loadQuests({ silent: true })
      }, ACTIVE_SYNC_MS)
      const onVisible = () => {
        if (document.visibilityState === 'visible') {
          loadQuests({ silent: true })
        }
      }
      document.addEventListener('visibilitychange', onVisible)
      return () => {
        window.clearInterval(timer)
        document.removeEventListener('visibilitychange', onVisible)
      }
    }
    return undefined
  }, [badgeOnly, isActive, loadQuests])

  return {
    kut: displayKut,
    sections,
    readyCount,
    npcName,
    npcEmoji,
    periodLabels,
    periodTimers,
    acceptRules,
    seedEconomy,
    farmCrops,
    initialLoading,
    refreshing,
    error,
    errorCode,
    claimingQuestId,
    acceptingQuestId,
    cancelingQuestId,
    claimingDailySeed,
    questMessage,
    claimQuest,
    acceptQuest,
    cancelQuest,
    claimDailySeed,
    reload: () => loadQuests({ silent: true }),
  }
}

export function useQuestBadge() {
  const { readyCount } = useQuests({ isActive: false, badgeOnly: true })
  return readyCount
}
