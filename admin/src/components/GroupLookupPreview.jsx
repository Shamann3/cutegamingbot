import { useEffect, useRef, useState } from 'react'
import { searchGroupsStudio } from '../lib/adminClient'

function normalizeQuery(raw) {
  let text = String(raw || '').trim()
  if (!text) return ''
  text = text.replace(/^@+/, '')
  const tme = text.match(/(?:https?:\/\/)?(?:t\.me|telegram\.me)\/(?:c\/)?([+\w.-]+)/i)
  if (tme) {
    const token = tme[1].replace(/^@/, '')
    if (/^\d+$/.test(token)) return `-100${token}`
    return token
  }
  return text.replace(/^https?:\/\//, '').replace(/\/+$/, '')
}

function pickFields(row) {
  if (!row) return null
  const chatId = row.chat_id ?? row.chatId
  const name = row.name || row.title || (chatId != null ? `Чат ${chatId}` : '')
  const username = row.username ? `@${String(row.username).replace(/^@/, '')}` : null
  return { chatId, name, username, raw: row }
}

/**
 * Превью группы: id / @username / t.me / название — как UserLookupPreview.
 */
export default function GroupLookupPreview({
  value,
  onChange,
  onResolved,
  placeholder = 'Id, @name, t.me/… или название',
  label = 'Группа',
}) {
  const [hits, setHits] = useState([])
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState(null)
  const timer = useRef(null)
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
        const data = await searchGroupsStudio(normalizeQuery(q) || q)
        const items = Array.isArray(data?.items) ? data.items : []
        setHits(items.slice(0, 6))
        const needle = normalizeQuery(q).toLowerCase()
        const exact = items.find((row) => String(row.chat_id) === needle)
          || items.find((row) => String(row.username || '').toLowerCase() === needle.replace(/^@/, ''))
          || items.find((row) => String(row.name || '').toLowerCase() === needle)
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

  const choose = (row) => {
    if (!row) return
    setPicked(row)
    onResolvedRef.current?.(row)
    const fields = pickFields(row)
    onChange?.(fields?.username || String(fields?.chatId || ''))
  }

  return (
    <div className="ulp-wrap glp-wrap">
      <label className="grp-field">
        <span>{label}</span>
        <input
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
        />
      </label>
      {loading && <p className="realm-copy">Ищем группу…</p>}
      {card && (
        <button type="button" className="ulp-card" onClick={() => choose(card.raw)}>
          <span className="ulp-avatar" aria-hidden>
            {(card.name || '?').slice(0, 1).toUpperCase()}
          </span>
          <span className="ulp-meta">
            <strong>{card.name}</strong>
            <em>
              {card.username || ''}
              {card.username && card.chatId != null ? ' · ' : ''}
              {card.chatId != null ? `#${card.chatId}` : ''}
            </em>
          </span>
        </button>
      )}
      {showList && (
        <ul className="ulp-hits" role="listbox">
          {list.map((item) => (
            <li key={item.chatId}>
              <button type="button" onClick={() => choose(item.raw)}>
                <strong>{item.name}</strong>
                <span>{item.username || `#${item.chatId}`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
