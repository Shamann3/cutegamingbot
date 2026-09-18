import { useEffect, useState } from 'react'
import { fetchNikaPulse } from '../lib/adminClient'

export default function NikaCrisisStrip({ enabled, onOpen, onPulse }) {
  const [pulse, setPulse] = useState(null)

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    const load = () => {
      if (document.visibilityState !== 'visible') return
      fetchNikaPulse()
        .then((data) => {
          if (cancelled) return
          setPulse(data)
          onPulse?.(data)
        })
        .catch(() => {
          if (!cancelled) onPulse?.({ openCritical: 0, crisis: false })
        })
    }
    load()
    const id = window.setInterval(load, 8000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [enabled, onPulse])

  if (!enabled || !pulse?.crisis) return null

  const starve = Array.isArray(pulse.starving) ? pulse.starving : []
  const count = Number(pulse.openCritical || 0) + starve.length

  return (
    <aside
      className="nika-crisis"
      role="alert"
      aria-live="assertive"
    >
      <div className="nika-crisis-pulse" aria-hidden="true" />
      <div className="nika-crisis-body">
        <p className="nika-crisis-kicker">Критично · только ты это видишь</p>
        <h2 className="nika-crisis-title">{pulse.headline || 'Ника не смогла закрыть ошибку'}</h2>
        {pulse.detail ? <p className="nika-crisis-detail">{pulse.detail}</p> : null}
        {starve.length > 0 && (
          <ul className="nika-crisis-list">
            {starve.slice(0, 4).map((g) => (
              <li key={g.chatId}>
                <strong>{g.name}</strong>
                <span>0 / {g.target} кут</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button type="button" className="nika-crisis-go" onClick={onOpen}>
        Открыть Нику
        {count > 0 ? <em>{count > 99 ? '99+' : count}</em> : null}
      </button>
    </aside>
  )
}
