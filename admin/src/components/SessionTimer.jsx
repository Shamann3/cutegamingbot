import { useCallback, useEffect, useRef, useState } from 'react'
import { getAdminSessionExpiryMs, hasTelegramInitData, refreshAdminSession } from '../lib/adminClient'

function formatRemaining(ms) {
  if (ms <= 0) return '00:00'
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function SessionTimer({ onExpired, compact = false }) {
  const [remainingMs, setRemainingMs] = useState(() => {
    const exp = getAdminSessionExpiryMs()
    return exp ? exp - Date.now() : -1
  })
  const [refreshing, setRefreshing] = useState(false)
  // Guard: fire onExpired exactly once per session lifetime.
  // Without this, the 1-second interval calls onExpired on every tick
  // after the token expires, spamming logout side-effects 60 times/minute.
  const expiredFiredRef = useRef(false)

  const tick = useCallback(() => {
    const exp = getAdminSessionExpiryMs()
    // В Telegram сессия держится сервером по initData (присылается на каждый
    // запрос), поэтому клиентский срок токена не должен никого разлогинивать —
    // иначе на телефоне (где токен не переживает перезагрузку WebView) панель
    // выкидывало бы на вход. Просто показываем состояние.
    if (hasTelegramInitData()) {
      setRemainingMs(exp ? exp - Date.now() : -1)
      return
    }
    if (!exp) {
      setRemainingMs(-1)
      return
    }
    const left = exp - Date.now()
    setRemainingMs(left)
    if (left <= 0 && !expiredFiredRef.current) {
      expiredFiredRef.current = true
      onExpired?.()
    }
  }, [onExpired])

  useEffect(() => {
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [tick])

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') tick()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [tick])

  useEffect(() => {
    refreshAdminSession()
      .then(() => tick())
      .catch(() => {})
  }, [tick])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await refreshAdminSession()
      // Reset guard so expiry can fire again on the new token
      expiredFiredRef.current = false
      tick()
    } catch {
      onExpired?.()
    } finally {
      setRefreshing(false)
    }
  }

  const telegramSession = remainingMs < 0
  const urgent = remainingMs > 0 && remainingMs < 5 * 60 * 1000

  return (
    <div
      className={`panel-session-timer${urgent ? ' panel-session-timer-urgent' : ''}${compact ? ' panel-session-timer-compact' : ''}`}
    >
      <div className="panel-session-timer-head">
        <p className="panel-shelf-label">Сессия</p>
        <p className="panel-session-value" aria-live="polite">
          {telegramSession ? 'Telegram' : formatRemaining(remainingMs)}
        </p>
      </div>
      <p className="panel-session-hint">
        {telegramSession
          ? 'Активна'
          : remainingMs <= 0
            ? 'Истекла'
            : urgent
              ? 'Скоро истечёт'
              : 'До выхода'}
      </p>
      <button
        type="button"
        className="panel-users-btn panel-session-refresh"
        disabled={refreshing}
        onClick={handleRefresh}
      >
        {refreshing ? '…' : 'Продлить'}
      </button>
    </div>
  )
}
