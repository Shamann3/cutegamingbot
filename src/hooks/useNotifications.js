import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import {
  ackNotifications,
  connectNotificationStream,
  fetchNotifications,
} from '../lib/notificationsClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { canAuthenticate } from '../lib/telegram'

const TOAST_MS = 5200
const MAX_VISIBLE = 3
const FALLBACK_POLL_MS = 45_000
const STREAM_RETRY_BASE_MS = 8_000
const STREAM_RETRY_MAX_MS = 120_000
const STREAM_LIMIT_RETRY_MS = 120_000
const USE_STREAM = import.meta.env.VITE_NOTIFICATION_STREAM !== 'false'

function streamRetryDelayMs(failures, isCapacityLimit = false) {
  const base = isCapacityLimit ? STREAM_LIMIT_RETRY_MS : STREAM_RETRY_BASE_MS
  const exponential = Math.min(base * (2 ** failures), STREAM_RETRY_MAX_MS)
  return exponential * (0.85 + Math.random() * 0.3)
}

function formatMarketSale(payload) {
  const emoji = payload.emoji ?? '📦'
  const name = payload.name ?? 'предмет'
  const qty = payload.quantity ?? 1
  const payout = payload.payout ?? 0
  return {
    title: 'Лот продан!',
    body: `${emoji} ${name} ×${qty}`,
    detail: `+${payout} КУТ на баланс`,
    kind: 'market_sale',
  }
}

function formatAdminMessage(payload) {
  return {
    title: payload.title ?? 'Сообщение',
    body: payload.body ?? '',
    detail: payload.detail || null,
    kind: 'admin_message',
  }
}

function mapNotification(item) {
  const payload = item.payload ?? {}
  if (item.eventType === 'market_sale' || payload.type === 'market_sale') {
    return {
      id: item.id,
      ...formatMarketSale(payload),
      balance: payload.balance ?? null,
      payout: payload.payout ?? null,
    }
  }
  if (item.eventType === 'admin_message' || payload.type === 'admin_message') {
    return {
      id: item.id,
      ...formatAdminMessage(payload),
    }
  }
  return {
    id: item.id,
    title: 'Уведомление',
    body: payload.name ?? 'Новое событие',
    detail: null,
    kind: 'generic',
    balance: payload.balance ?? null,
    payout: payload.payout ?? null,
  }
}

export function useNotifications() {
  const { syncFromNotification } = usePlayerSync()
  const [toasts, setToasts] = useState([])
  const seenRef = useRef(new Set())
  const ackQueueRef = useRef(new Set())
  const dismissTimersRef = useRef(new Map())
  const streamAbortRef = useRef(null)
  const streamRetryRef = useRef(null)
  const streamActiveRef = useRef(false)
  const streamFailuresRef = useRef(0)
  const startStreamRef = useRef(() => {})

  const scheduleStreamRetry = useCallback((isCapacityLimit = false) => {
    if (streamRetryRef.current) return

    const delay = streamRetryDelayMs(streamFailuresRef.current, isCapacityLimit)
    streamFailuresRef.current += 1

    streamRetryRef.current = window.setTimeout(() => {
      streamRetryRef.current = null
      startStreamRef.current()
    }, delay)
  }, [])

  const dismissToast = useCallback((id) => {
    const timer = dismissTimersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      dismissTimersRef.current.delete(id)
    }
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((toast) => {
    setToasts((prev) => {
      const next = [...prev, { ...toast, entering: true }]
      return next.slice(-MAX_VISIBLE)
    })

    requestAnimationFrame(() => {
      setToasts((prev) =>
        prev.map((item) => (item.id === toast.id ? { ...item, entering: false } : item)),
      )
    })

    const timer = setTimeout(() => dismissToast(toast.id), TOAST_MS)
    dismissTimersRef.current.set(toast.id, timer)
  }, [dismissToast])

  const flushAck = useCallback(async () => {
    const ids = [...ackQueueRef.current].filter((id) => id > 0)
    if (!ids.length) return
    ackQueueRef.current.clear()
    try {
      await ackNotifications(ids)
    } catch {
      ids.forEach((id) => ackQueueRef.current.add(id))
    }
  }, [])

  const handleNotifications = useCallback((items) => {
    const fresh = []
    for (const item of items ?? []) {
      if (!item?.id || seenRef.current.has(item.id)) continue
      seenRef.current.add(item.id)
      if (item.id > 0) ackQueueRef.current.add(item.id)
      fresh.push(mapNotification(item))
    }
    if (!fresh.length) return

    fresh.forEach((toast) => {
      showToast(toast)
      if (toast.balance != null || toast.payout != null) {
        syncFromNotification({ balance: toast.balance, payout: toast.payout })
      }
    })
    flushAck()
  }, [flushAck, showToast, syncFromNotification])

  const pollFallback = useCallback(async () => {
    if (!canAuthenticate()) return
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
    try {
      const data = await fetchNotifications()
      handleNotifications(data.notifications)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'auth') return
    }
  }, [handleNotifications])

  const stopStream = useCallback(() => {
    streamActiveRef.current = false
    if (streamRetryRef.current) {
      clearTimeout(streamRetryRef.current)
      streamRetryRef.current = null
    }
    if (streamAbortRef.current) {
      streamAbortRef.current.abort()
      streamAbortRef.current = null
    }
  }, [])

  const startStream = useCallback(() => {
    if (!USE_STREAM || !canAuthenticate() || streamActiveRef.current) return
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return

    stopStream()
    streamActiveRef.current = true
    const controller = new AbortController()
    streamAbortRef.current = controller

    connectNotificationStream({
      signal: controller.signal,
      onOpen: () => {
        streamFailuresRef.current = 0
      },
      onNotification: (item) => handleNotifications([item]),
    })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof ApiError && err.code === 'auth') {
          stopStream()
          return
        }
        const capacityLimit = err instanceof ApiError
          && err.status === 503
          && err.code === 'sse_limit'
        scheduleStreamRetry(capacityLimit)
      })
      .finally(() => {
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null
        }
        streamActiveRef.current = false
        if (
          !controller.signal.aborted
          && USE_STREAM
          && canAuthenticate()
          && document.visibilityState === 'visible'
          && !streamRetryRef.current
        ) {
          scheduleStreamRetry(false)
        }
      })
  }, [handleNotifications, scheduleStreamRetry, stopStream])

  startStreamRef.current = startStream

  useEffect(() => {
    if (!canAuthenticate()) return undefined

    pollFallback()
    startStream()

    const fallbackId = window.setInterval(pollFallback, FALLBACK_POLL_MS)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        streamFailuresRef.current = 0
        pollFallback()
        startStream()
      } else {
        stopStream()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      clearInterval(fallbackId)
      document.removeEventListener('visibilitychange', onVisibility)
      stopStream()
      dismissTimersRef.current.forEach((timer) => clearTimeout(timer))
      dismissTimersRef.current.clear()
      flushAck()
    }
  }, [flushAck, pollFallback, startStream, stopStream])

  return { toasts, dismissToast }
}
