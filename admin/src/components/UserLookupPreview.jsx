import { useEffect, useRef, useState } from 'react'
import { searchAdminUsers } from '../lib/adminClient'

function fmt(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(v)
}

function pickFields(u) {
  if (!u) return null
  const uid = Number(u.userId ?? u.user_id)
  const name = u.displayName || u.firstName || u.first_name || u.name || (uid ? `Игрок ${uid}` : '')
  const uname = u.username ? `@${String(u.username).replace(/^@/, '')}` : null
  return { uid, name, uname, balance: u.balance, banned: u.banned, raw: u }
}

/**
 * Мини-превью игрока над полем ввода (id / @username / имя).
 * Клик по карточке → onOpenUser(userId).
 * Можно выбрать из списка совпадений.
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
        setHits(items.slice(0, 6))
        const asId = q.replace(/^@/, '')
        const exact = items.find((u) => String(u.userId || u.user_id) === asId)
          || items.find((u) => String(u.username || '').toLowerCase() === asId.toLowerCase())
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

  const card = pickFields(picked)
  const list = hits.map(pickFields).filter(Boolean)
  const showList = !picked && list.length > 1
  const showCard = Boolean(card)

  const choose = (u) => {
    if (!u) return
    setPicked(u)
    onResolvedRef.current?.(u)
    const id = String(u.userId ?? u.user_id ?? '')
    const un = u.username ? `@${String(u.username).replace(/^@/, '')}` : id
    onChange?.(un || id)
  }

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

      {showCard && (
        <button
          type="button"
          className="ulp-card"
          onClick={() => card.uid && onOpenUser?.(card.uid)}
          title="Открыть карточку игрока"
        >
          <span className="ulp-avatar" aria-hidden>
            {(card.name || '?').slice(0, 1).toUpperCase()}
          </span>
          <span className="ulp-meta">
            <strong>{card.name}</strong>
            <em>
              {card.uname || `id ${card.uid}`}
              {card.balance != null ? ` · ${fmt(card.balance)} кут` : ''}
              {card.banned ? ' · бан в боте' : ''}
            </em>
          </span>
          <span className="ulp-go">→</span>
          {loading ? <span className="ulp-loading">…</span> : null}
        </button>
      )}

      {showList && (
        <div className="ulp-hits" role="listbox">
          {list.map((h) => (
            <button
              key={h.uid}
              type="button"
              className="ulp-hit"
              role="option"
              onClick={() => choose(h.raw)}
            >
              <strong>{h.name}</strong>
              <em>{h.uname || `id ${h.uid}`}{h.banned ? ' · бан' : ''}</em>
            </button>
          ))}
        </div>
      )}

      {!showCard && !showList && loading ? (
        <span className="ulp-loading-inline">Ищем…</span>
      ) : null}
    </div>
  )
}
