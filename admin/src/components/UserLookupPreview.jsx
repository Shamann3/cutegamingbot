import { useEffect, useRef, useState } from 'react'
import { glanceAdminUser, searchAdminUsers } from '../lib/adminClient'
import { CopyableId, CopyableUsername } from './Copyable'

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
  return { uid, name, uname, balance: u.balance, banned: u.banned, outside: Boolean(u.outside), raw: u }
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
  onHint,
  allowOutside = false,
  chatId = null,
  placeholder = 'ID, @username или имя',
  label = 'Игрок',
}) {
  const [hits, setHits] = useState([])
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState(null)
  const [hint, setHint] = useState('')
  const timer = useRef(null)
  const wrapRef = useRef(null)
  const onResolvedRef = useRef(onResolved)
  const onHintRef = useRef(onHint)
  onResolvedRef.current = onResolved
  onHintRef.current = onHint

  useEffect(() => {
    let cancelled = false
    const q = String(value || '').trim()
    if (timer.current) window.clearTimeout(timer.current)
    if (q.length < 2) {
      setHits([])
      setPicked(null)
      setHint('')
      onResolvedRef.current?.(null)
      onHintRef.current?.('')
      return undefined
    }
    timer.current = window.setTimeout(async () => {
      setLoading(true)
      try {
        const data = await searchAdminUsers(q)
        if (cancelled) return
        const items = Array.isArray(data?.results) ? data.results : Array.isArray(data?.items) ? data.items : []
        setHits(items.slice(0, 6))
        const asId = q.replace(/^@/, '')
        const exact = items.find((u) => String(u.userId || u.user_id) === asId)
          || items.find((u) => String(u.username || '').toLowerCase() === asId.toLowerCase())
          || (items.length === 1 ? items[0] : null)
        if (exact) {
          setPicked(exact)
          setHint('')
          onResolvedRef.current?.(exact)
          onHintRef.current?.('')
          return
        }
        if (!allowOutside || items.length > 0) {
          setPicked(null)
          setHint('')
          onResolvedRef.current?.(null)
          onHintRef.current?.('')
          return
        }
        const glance = await glanceAdminUser(q, chatId)
        if (cancelled) return
        const person = glance?.user
        if (person) {
          setHits([person])
          setPicked(person)
          setHint(glance.message || '')
          onResolvedRef.current?.(person)
          onHintRef.current?.(glance.message || '')
          return
        }
        setHits([])
        setPicked(null)
        setHint(glance?.message || '')
        onResolvedRef.current?.(null)
        onHintRef.current?.(glance?.message || '')
      } catch {
        if (cancelled) return
        setHits([])
        setPicked(null)
        setHint('')
        onResolvedRef.current?.(null)
        onHintRef.current?.('')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 280)
    return () => {
      cancelled = true
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [value, allowOutside, chatId])

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
              {card.uname ? <CopyableUsername value={card.uname} /> : <CopyableId value={card.uid} />}
              {card.uname && card.uid ? <> · <CopyableId value={card.uid} /></> : null}
              {card.balance != null ? ` · ${fmt(card.balance)} кут` : ''}
              {card.outside ? ' · ещё не в Куте' : ''}
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
              <em>
                {h.uname ? <CopyableUsername value={h.uname} /> : <CopyableId value={h.uid} />}
                {h.uname && h.uid ? <> · <CopyableId value={h.uid} /></> : null}
                {h.banned ? ' · бан' : ''}
              </em>
            </button>
          ))}
        </div>
      )}

      {!showCard && !showList && loading ? (
        <span className="ulp-loading-inline">Ищем…</span>
      ) : null}
      {hint ? <p className="ulp-note" role="status">{hint}</p> : null}
    </div>
  )
}
