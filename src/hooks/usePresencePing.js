import { useEffect, useRef } from 'react'
import { canAuthenticate } from '../lib/telegram'
import { leavePresence, pingPresence } from '../lib/presenceClient'

const PING_MS = Number(import.meta.env.VITE_ONLINE_PING_MS) || 20000

export function usePresencePing({ enabled = true } = {}) {
  const onlineRef = useRef(false)

  useEffect(() => {
    if (!enabled || !canAuthenticate()) return

    let intervalId = null

    const goOnline = () => {
      onlineRef.current = true
      pingPresence().catch(() => {})
    }

    const goOffline = () => {
      if (!onlineRef.current) return
      onlineRef.current = false
      leavePresence()
    }

    const startPingLoop = () => {
      if (intervalId != null) return
      goOnline()
      intervalId = window.setInterval(goOnline, PING_MS)
    }

    const stopPingLoop = () => {
      if (intervalId != null) {
        window.clearInterval(intervalId)
        intervalId = null
      }
    }

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        startPingLoop()
        return
      }
      stopPingLoop()
      goOffline()
    }

    const onPageHide = () => {
      stopPingLoop()
      goOffline()
    }

    if (document.visibilityState === 'visible') {
      startPingLoop()
    }

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', onPageHide)

    const tg = window.Telegram?.WebApp
    const onTgVisibility = (payload) => {
      const visible = typeof payload === 'object' && payload != null && 'is_visible' in payload
        ? Boolean(payload.is_visible)
        : Boolean(payload)
      if (visible) {
        startPingLoop()
      } else {
        stopPingLoop()
        goOffline()
      }
    }

    tg?.onEvent?.('visibility_changed', onTgVisibility)

    return () => {
      stopPingLoop()
      goOffline()
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', onPageHide)
      tg?.offEvent?.('visibility_changed', onTgVisibility)
    }
  }, [enabled])
}
