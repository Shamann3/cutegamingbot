import { useEffect, useMemo, useState } from 'react'
import FocusWindow from './FocusWindow'
import PhotoLook from './PhotoLook'
import { payLabel, sortLabel } from '../lib/deedSort'
import UserLookupPreview from './UserLookupPreview'
import OpenUserLink from './OpenUserLink'

const LOOK = {
  ban: { label: 'Бан', color: '#ef4444' },
  unban: { label: 'Разбан', color: '#22c55e' },
  mute: { label: 'Мут', color: '#f97316' },
  unmute: { label: 'Размут', color: '#2dd4bf' },
  kick: { label: 'Кик', color: '#a855f7' },
  warn: { label: 'Варн', color: '#eab308' },
  unwarn: { label: 'Разварн', color: '#84cc16' },
  voice: { label: 'Голос', color: '#60a5fa' },
  unvoice: { label: 'Голос снова', color: '#93c5fd' },
}

const FAMILY = {
  mute: ['mute', 'unmute'],
  ban: ['ban', 'unban'],
  kick: ['kick'],
  warn: ['warn', 'unwarn'],
  voice: ['voice', 'unvoice'],
}

const FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'mute', label: 'Муты' },
  { id: 'ban', label: 'Баны' },
  { id: 'kick', label: 'Кики' },
  { id: 'warn', label: 'Варны' },
  { id: 'near', label: 'Близко к блокировке' },
  { id: 'far', label: 'Далеко от блокировки' },
  { id: 'repeat', label: 'Повторные' },
]

function when(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function lookFor(action) {
  const key = String(action || '').toLowerCase()
  return LOOK[key] || { label: key || 'Запись', color: '#f4f4f4' }
}

function undoAction(action) {
  const key = String(action || '').toLowerCase()
  if (key === 'ban') return { id: 'unban', label: 'Разбанить' }
  if (key === 'mute') return { id: 'unmute', label: 'Размутить' }
  if (key === 'voice') return { id: 'unvoice', label: 'Вернуть голос' }
  if (key === 'warn') return { id: 'warn', label: 'Ещё варн' }
  return null
}

/** Архив группы: фильтры + наказание/снятие здесь, без прыжка в «Активность». */
export default function GroupArchive({
  rows,
  repeats = new Map(),
  watch,
  actions = [],
  onAct,
  seedQuery = '',
  onOpenUser,
}) {
  const [filter, setFilter] = useState('all')
  const [openId, setOpenId] = useState(null)
  const [userId, setUserId] = useState(seedQuery || '')
  const [resolvedId, setResolvedId] = useState(null)
  const [action, setAction] = useState(actions[0]?.id || 'mute')
  const [hours, setHours] = useState('1')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (seedQuery) setUserId(String(seedQuery))
  }, [seedQuery])

  useEffect(() => {
    if (actions.length && !actions.some((item) => item.id === action)) {
      setAction(actions[0].id)
    }
  }, [actions, action])

  const warnMap = useMemo(() => {
    const map = new Map()
    for (const person of watch || []) {
      map.set(Number(person.userId), Number(person.warns) || 0)
    }
    return map
  }, [watch])

  const items = useMemo(() => {
    const list = rows || []
    if (filter === 'all') return list
    if (filter === 'repeat') {
      return list.filter((row) => (repeats.get(Number(row.target_user_id)) || 0) >= 2)
    }
    if (filter === 'near') {
      return list.filter((row) => (warnMap.get(Number(row.target_user_id)) || 0) >= 2)
    }
    if (filter === 'far') {
      return list.filter((row) => (warnMap.get(Number(row.target_user_id)) || 0) <= 1)
    }
    return list.filter((row) => (FAMILY[filter] || []).includes(String(row.action || '').toLowerCase()))
  }, [rows, filter, repeats, warnMap])

  const selected = actions.find((item) => item.id === action) || actions[0]

  const submit = async (event) => {
    event.preventDefault()
    if (!onAct || !selected) return
    setBusy(true)
    setError('')
    try {
      await onAct({
        userId: resolvedId || userId.trim(),
        action: selected.id,
        hours: selected.needsUntil ? hours : null,
        reason: reason.trim(),
      })
      setReason('')
    } catch (err) {
      setError(err.message || 'Не удалось выполнить')
    } finally {
      setBusy(false)
    }
  }

  const quick = async (targetId, actId) => {
    if (!onAct || !actId) return
    const why = window.prompt('Причина (обязательно)')
    if (why == null) return
    if (!String(why).trim()) {
      setError('Нужна причина')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onAct({
        userId: String(targetId),
        action: actId,
        hours: actId === 'warn' ? '24' : null,
        reason: String(why).trim(),
      })
    } catch (err) {
      setError(err.message || 'Не удалось выполнить')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="g-arc-wrap">
      {error && <p className="realm-alert" role="alert">{error}</p>}

      <div className="realm-actions e-seg" aria-label="Фильтр архива">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={filter === item.id ? 'is-on' : ''}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {actions.length > 0 && (
        <form id="g-arc-punish" className="realm-form g-arc-punish" onSubmit={submit}>
          <h3 className="realm-h">Наказать в этом чате</h3>
          <p className="realm-copy">Id, @username, ссылка или имя. Причина обязательна.</p>
          <UserLookupPreview
            value={userId}
            onChange={setUserId}
            onResolved={(u) => setResolvedId(u ? Number(u.userId ?? u.user_id) : null)}
            onOpenUser={onOpenUser}
            placeholder="id, @name, t.me/… или имя"
            label="Кто"
          />
          <div className="realm-actions e-seg">
            {actions.map((item) => (
              <button
                key={item.id}
                type="button"
                className={selected?.id === item.id ? 'is-on' : ''}
                onClick={() => setAction(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {selected?.needsUntil && (
            <label>
              Часы
              <input inputMode="decimal" value={hours} onChange={(event) => setHours(event.target.value)} />
            </label>
          )}
          <label>
            Причина
            <input value={reason} onChange={(event) => setReason(event.target.value)} required />
          </label>
          <button type="submit" className="realm-back" disabled={busy}>
            {busy ? 'Запись…' : 'Выполнить'}
          </button>
        </form>
      )}

      {Array.isArray(watch) && watch.length > 0 && filter === 'near' && (
        <p className="realm-copy">
          С активными варнами: {watch.map((p) => `${p.name || p.userId} (${p.warns}/3)`).join(' · ')}
        </p>
      )}

      {items.length === 0 && <p className="realm-copy">В этом чате таких записей пока нет.</p>}
      <div className="g-arc-grid">
        {items.map((row, index) => {
          const look = lookFor(row.action)
          const id = row.id ?? `${row.at || index}`
          const open = openId === id
          const player = row.targetName || (row.target_user_id ? `#${row.target_user_id}` : '—')
          const undo = undoAction(row.action)
          const canUndo = undo && actions.some((item) => item.id === undo.id)
          return (
            <article
              key={id}
              className={open ? 'g-arc-card is-open' : 'g-arc-card'}
              style={{ '--cc': look.color }}
            >
              <button type="button" className="g-arc-hit" onClick={() => setOpenId(open ? null : id)} aria-expanded={open}>
                <span className="g-arc-badge" style={{ background: look.color }}>{look.label}</span>
                <time>{when(row.at || row.created_at)}</time>
                <span className="g-arc-who">
                  <span>
                    <small>Выдал</small>
                    <strong>{row.admin || '—'}</strong>
                  </span>
                  <span aria-hidden="true">→</span>
                  <span>
                    <small>В чате</small>
                    <OpenUserLink userId={row.target_user_id} name={row.targetName} onOpenUser={onOpenUser} />
                  </span>
                </span>
                <span className={row.reason ? 'g-arc-reason' : 'g-arc-reason is-empty'}>
                  {row.reason || 'Причина не указана'}
                </span>
                <span className="g-arc-tags">
                  {(repeats.get(Number(row.target_user_id)) || 0) >= 2 && (
                    <span>В архиве {repeats.get(Number(row.target_user_id))} раз</span>
                  )}
                  {row.hasProof && <span>Есть фото</span>}
                  {sortLabel(row.sortVerdict) && <span>{sortLabel(row.sortVerdict)}</span>}
                  {payLabel(row.payStatus) && <span>{payLabel(row.payStatus)}</span>}
                  <span>{open ? 'Скрыть' : 'Открыть'}</span>
                </span>
              </button>
              {open && (
                <FocusWindow
                  title={look.label}
                  subtitle={when(row.at || row.created_at)}
                  onClose={() => setOpenId(null)}
                >
                  <p className="realm-copy">{row.reason || 'Причина не указана'}</p>
                  <div className="g-arc-tools">
                    {row.target_user_id && (
                      <button
                        type="button"
                        className="realm-text-act"
                        onClick={() => {
                          setOpenId(null)
                          setUserId(String(row.target_user_id))
                          window.setTimeout(() => {
                            document.getElementById('g-arc-punish')?.scrollIntoView({
                              block: 'nearest',
                              behavior: 'smooth',
                            })
                          }, 40)
                        }}
                      >
                        Наказать
                      </button>
                    )}
                    {canUndo && row.target_user_id && (
                      <button
                        type="button"
                        className="realm-back"
                        disabled={busy}
                        onClick={() => quick(row.target_user_id, undo.id)}
                      >
                        {undo.label}
                      </button>
                    )}
                  </div>
                  {row.proofMediaId
                    ? <PhotoLook fileId={row.proofMediaId} eager alt="Фото доказательства" />
                    : <p className="realm-copy">Фото доказательства нет.</p>}
                </FocusWindow>
              )}
              <span className="g-arc-stripe" style={{ background: look.color }} />
            </article>
          )
        })}
      </div>
    </div>
  )
}
