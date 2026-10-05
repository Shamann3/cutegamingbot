import { useEffect, useMemo, useState } from 'react'
import FocusWindow from './FocusWindow'
import PhotoLook from './PhotoLook'
import { payLabel, sortLabel } from '../lib/deedSort'
import { arrivalLine, hiddenLine } from '../lib/liveMerge'
import UserLookupPreview from './UserLookupPreview'
import OpenUserLink from './OpenUserLink'

const LOOK = {
  ban: { label: 'Бан', color: '#ef4444' },
  unban: { label: 'Разбан', color: '#22c55e' },
  mute: { label: 'Мут', color: '#f97316' },
  unmute: { label: 'Размут', color: '#2dd4bf' },
  kick: { label: 'Кик', color: '#a855f7' },
  warn: { label: 'Предупреждение', color: '#eab308' },
  unwarn: { label: 'Снято', color: '#84cc16' },
  voice: { label: 'Без голоса', color: '#60a5fa' },
  unvoice: { label: 'Голос вернули', color: '#93c5fd' },
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
  { id: 'warn', label: 'Предупреждения' },
  { id: 'near', label: 'Скоро бан' },
  { id: 'far', label: 'Мало предупреждений' },
  { id: 'repeat', label: 'Повторные' },
]

const FILTER_HINT = {
  mute: 'Муты и снятые муты.',
  ban: 'Баны и снятые баны.',
  kick: 'Только кики. Кик из чата снять нельзя.',
  warn: 'Предупреждения. Три активных в этом чате — бан.',
  near: 'Два или три предупреждения. На третьем чат банит сам.',
  far: 'Ноль или одно предупреждение.',
  repeat: 'Кого в этом списке наказывали больше одного раза.',
}

function actVerb(id, label) {
  const named = {
    mute: 'Выдать мут',
    unmute: 'Снять мут',
    ban: 'Выдать бан',
    unban: 'Снять бан',
    kick: 'Кикнуть из чата',
    warn: 'Выдать предупреждение',
    voice: 'Забрать голос',
    unvoice: 'Вернуть голос',
  }
  return named[id] || label || 'Выполнить'
}

function stuckNote(action) {
  const key = String(action || '').toLowerCase()
  if (key === 'warn') return 'Снять нельзя. Третье активное предупреждение в этом чате — бан.'
  if (key === 'kick') return 'Кик снять нельзя: человека уже вывело из чата.'
  return ''
}

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

function rowShown(row, filter, repeats, warnMap) {
  if (filter === 'all') return true
  if (filter === 'repeat') return (repeats.get(Number(row.target_user_id)) || 0) >= 2
  if (filter === 'near') return (warnMap.get(Number(row.target_user_id)) || 0) >= 2
  if (filter === 'far') return (warnMap.get(Number(row.target_user_id)) || 0) <= 1
  return (FAMILY[filter] || []).includes(String(row.action || '').toLowerCase())
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
  arrived = [],
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
  const [liftId, setLiftId] = useState(null)
  const [liftReason, setLiftReason] = useState('')

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
    return list.filter((row) => rowShown(row, filter, repeats, warnMap))
  }, [rows, filter, repeats, warnMap])

  const freshIds = useMemo(() => new Set((arrived || []).map((row) => Number(row.id))), [arrived])
  const liveText = useMemo(() => {
    if (!arrived?.length) return ''
    const visible = arrived.filter((row) => rowShown(row, filter, repeats, warnMap))
    if (!visible.length) return hiddenLine(arrived[0])
    return arrivalLine(visible)
  }, [arrived, filter, repeats, warnMap])

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

  const lift = async (event, targetId, actId) => {
    event.preventDefault()
    if (!onAct || !actId) return
    if (!liftReason.trim()) {
      setError('Нужна причина')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onAct({
        userId: String(targetId),
        action: actId,
        hours: null,
        reason: liftReason.trim(),
      })
      setLiftId(null)
      setLiftReason('')
      setOpenId(null)
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
      {FILTER_HINT[filter] && <p className="realm-copy">{FILTER_HINT[filter]}</p>}
      {liveText && <p className="g-arc-live" role="status">{liveText}</p>}

      {actions.length > 0 && (
        <form id="g-arc-punish" className="realm-form g-arc-punish" onSubmit={submit}>
          <h3 className="realm-h">Новое наказание</h3>
          <p className="realm-copy">Найдите человека и выберите, что сделать. Без причины кнопка внизу не сработает.</p>
          <UserLookupPreview
            value={userId}
            onChange={setUserId}
            onResolved={(u) => setResolvedId(u ? Number(u.userId ?? u.user_id) : null)}
            onOpenUser={onOpenUser}
            placeholder="id, @name, t.me/… или имя"
            label="Кого наказать"
          />
          <div className="g-arc-acts" role="group" aria-label="Какое наказание">
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
              Сколько часов держать
              <input inputMode="decimal" value={hours} onChange={(event) => setHours(event.target.value)} placeholder="например, 1" />
            </label>
          )}
          <label>
            Причина
            <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="что человек сделал" required />
          </label>
          <button type="submit" className="realm-back" disabled={busy || !selected}>
            {busy ? 'Запись…' : actVerb(selected?.id, selected?.label)}
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
          const undo = undoAction(row.action)
          const canUndo = undo && actions.some((item) => item.id === undo.id)
          return (
            <article
              key={id}
              className={`g-arc-card${open ? ' is-open' : ''}${freshIds.has(Number(id)) ? ' is-arrive' : ''}`}
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
                    <small>Кому</small>
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
                  <span>{open ? 'Скрыть' : 'Подробнее'}</span>
                </span>
              </button>
              {canUndo && undo.id !== 'warn' && row.target_user_id ? (
                <div className="g-arc-actions">
                  {liftId === id ? (
                    <form className="g-arc-lift" onSubmit={(event) => lift(event, row.target_user_id, undo.id)}>
                      <label>
                        Причина снятия
                        <input
                          value={liftReason}
                          onChange={(event) => setLiftReason(event.target.value)}
                          placeholder="зачем снимаете"
                          required
                        />
                      </label>
                      <p className="realm-copy">Без текста снятие не уйдёт.</p>
                      <div className="g-arc-lift-row">
                        <button type="submit" className="sec-btn" disabled={busy}>
                          {busy ? 'Снимаем…' : undo.label}
                        </button>
                        <button
                          type="button"
                          className="sec-btn sec-btn-ghost"
                          onClick={() => { setLiftId(null); setLiftReason('') }}
                        >
                          Отмена
                        </button>
                      </div>
                    </form>
                  ) : (
                    <button
                      type="button"
                      className="sec-btn g-arc-lift-open"
                      disabled={busy}
                      onClick={() => { setLiftId(id); setLiftReason(''); setOpenId(null) }}
                    >
                      {undo.label}
                    </button>
                  )}
                </div>
              ) : stuckNote(row.action) ? (
                <p className="g-arc-note">{stuckNote(row.action)}</p>
              ) : null}
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
                        className="sec-btn sec-btn-ghost"
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
                        Наказать этого человека
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
