import { useEffect, useRef, useState } from 'react'
import { searchAdminUsers } from '../lib/adminClient'

function fmt(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(v)
}

/**
 * Мини-превью игрока над полем ввода (id / @username / имя).
 * Клик → onOpenUser(userId).
 */
export default function UserLookupPreview({
  value,
  onChange,
  onResolved,
  onOpenUser,
  placeholder = 'ID, @username или имя',
  label = 'Игрок',
}) {
  const [hits, setHits] = useState([])
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState(null)
  const timer = useRef(null)
  const wrapRef = useRef(null)
  const onResolvedRef = useRef(onResolved)
  onResolvedRef.current = onResolved

  useEffect(() => {
    const q = String(value || '').trim()
    if (timer.current) window.clearTimeout(timer.current)
    if (q.length < 2) {
      setHits([])
      setPicked(null)
      onResolvedRef.current?.(null)
      return undefined
    }
    timer.current = window.setTimeout(async () => {
      setLoading(true)
      try {
        const data = await searchAdminUsers(q)
        const items = Array.isArray(data?.results) ? data.results : Array.isArray(data?.items) ? data.items : []
        setHits(items.slice(0, 5))
        const asId = q.replace(/^@/, '')
        const exact = items.find((u) => String(u.userId || u.user_id) === asId)
          || (items.length === 1 ? items[0] : null)
        if (exact) {
          setPicked(exact)
          onResolvedRef.current?.(exact)
        } else {
          setPicked(null)
          onResolvedRef.current?.(null)
        }
      } catch {
        setHits([])
        setPicked(null)
        onResolvedRef.current?.(null)
      } finally {
        setLoading(false)
      }
    }, 280)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [value])

  const show = picked || (hits.length > 0 && String(value || '').trim().length >= 2)

  const card = picked || hits[0]
  const uid = card ? Number(card.userId ?? card.user_id) : null
  const name = card?.displayName || card?.firstName || card?.first_name || card?.name || (uid ? `Игрок ${uid}` : '')
  const uname = card?.username ? `@${String(card.username).replace(/^@/, '')}` : null

  return (
    <div className="ulp-wrap" ref={wrapRef}>
      <label className="grp-field">
        <span>{label}</span>
        <input
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
        />
      </label>

      {show && card && (
        <button
          type="button"
          className="ulp-card"
          onClick={() => uid && onOpenUser?.(uid)}
          title="Открыть карточку игрока"
        >
          <span className="ulp-avatar" aria-hidden>
            {(name || '?').slice(0, 1).toUpperCase()}
          </span>
          <span className="ulp-meta">
            <strong>{name}</strong>
            <em>
              {uname || `id ${uid}`}
              {card.balance != null ? ` · ${fmt(card.balance)} кут` : ''}
              {card.banned ? ' · бан в боте' : ''}
            </em>
          </span>
          <span className="ulp-go">→</span>
          {loading ? <span className="ulp-loading">…</span> : null}
        </button>
      )}
    </div>
  )
}
