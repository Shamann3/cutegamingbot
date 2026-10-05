import { useEffect, useRef, useState } from 'react'
import { fetchPersonHistory } from '../lib/adminClient'
import { playMeme } from '../lib/memeSounds'
import { PUNISH_RIGHTS } from '../lib/realmRights'
import { spanToSend, speakSpan } from '../lib/spanClock'
import FocusWindow from './FocusWindow'
import PhotoLook from './PhotoLook'
import SpanClock from './SpanClock'

const LABEL = {
  ban: 'Бан',
  banall: 'Баналл',
  banfull: 'Банфулл',
  bot_ban: 'Банфулл',
  unban: 'Разбан',
  unbanall: 'Разбан',
  bot_unban: 'Разбан',
  mute: 'Мут',
  muteall: 'Муталл',
  unmute: 'Размут',
  unmuteall: 'Размут',
  kick: 'Кик',
  kickall: 'Кикалл',
  warn: 'Предупреждение',
  warnall: 'Варналл',
  warnfull: 'Варнфулл',
  unwarn: 'Снято',
  voice: 'Без голоса',
  unvoice: 'Голос вернули',
}

function labelOf(action) {
  const key = String(action || '').toLowerCase()
  return LABEL[key] || key || 'Запись'
}

function spanOf(row) {
  const key = String(row.action || '').toLowerCase()
  const scope = String(row.scope || '').toLowerCase()
  if (['banfull', 'bot_ban', 'warnfull', 'bot_unban'].includes(key) || scope === 'full') return 'Весь проект'
  if (['banall', 'muteall', 'kickall', 'warnall', 'unbanall', 'unmuteall'].includes(key) || scope === 'all' || !row.chatId) {
    return 'Официальные группы'
  }
  return 'Этот чат'
}

function when(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const CHAT_SCOPE = Object.fromEntries(
  PUNISH_RIGHTS.map((item) => [item.id.replace('punish_', ''), item.hint]),
)

function issueVerb(selected, spanSec) {
  const name = selected?.label || 'наказание'
  if (!selected?.needsUntil) return `Выдать: ${name}`
  const sent = spanToSend(spanSec)
  return sent ? `Выдать: ${name} · ${speakSpan(sent)}` : `Выдать: ${name}`
}

function held(row) {
  const seconds = Number(row?.seconds || 0)
  const minutes = Number(row?.minutes || 0)
  const total = seconds > 0 ? seconds : (minutes > 0 ? minutes * 60 : 0)
  const said = speakSpan(total)
  return said ? `на ${said}` : ''
}

function liftOf(action) {
  const key = String(action || '').toLowerCase()
  if (key === 'ban' || key === 'banall' || key === 'banfull' || key === 'bot_ban') return { id: 'unban', label: 'Разбанить' }
  if (key === 'mute' || key === 'muteall') return { id: 'unmute', label: 'Размутить' }
  if (key === 'voice') return { id: 'unvoice', label: 'Вернуть голос' }
  return null
}

function issueList(actions, wide) {
  const local = (actions || []).filter((item) => item?.id && !String(item.id).startsWith('un'))
  const extra = (wide || []).filter((item) => item?.id && !local.some((row) => row.id === item.id))
  return { local, wide: extra, all: [...local, ...extra] }
}

function ChipRow({ items, selectedId, onPick, label }) {
  if (!items.length) return null
  return (
    <div className="person-issue-block">
      <p className="person-issue-title">{label}</p>
      <div className="person-acts" role="group" aria-label={label}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={selectedId === item.id ? 'is-on' : ''}
            aria-pressed={selectedId === item.id}
            onClick={() => onPick(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function PersonPunish({
  chatId,
  userId,
  actions = [],
  wide = [],
  onAct,
  watch = [],
  onClose,
}) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [freshId, setFreshId] = useState(null)
  const offered = issueList(actions, wide)
  const [action, setAction] = useState(offered.all[0]?.id || '')
  const spanRef = useRef(3600)
  const [spanSec, setSpanSec] = useState(3600)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const [liftId, setLiftId] = useState(null)
  const [liftReason, setLiftReason] = useState('')
  const selected = offered.all.find((item) => item.id === action) || offered.all[0]
  const scopeHint = selected?.hint || CHAT_SCOPE[selected?.id] || ''
  const warns = (watch || []).find((item) => Number(item.userId) === Number(userId))

  useEffect(() => {
    const next = issueList(actions, wide).all
    if (next.length && !next.some((item) => item.id === action)) setAction(next[0].id)
  }, [actions, wide, action])

  useEffect(() => {
    if (!chatId || !userId) return undefined
    let stop = false
    setLoading(true)
    setError('')
    fetchPersonHistory(chatId, userId)
      .then((data) => { if (!stop) setReport(data) })
      .catch((err) => { if (!stop) setError(err.message || 'История не открылась') })
      .finally(() => { if (!stop) setLoading(false) })
    return () => { stop = true }
  }, [chatId, userId])

  async function reload() {
    const data = await fetchPersonHistory(chatId, userId)
    setReport(data)
    return data
  }

  async function submit(event) {
    event.preventDefault()
    if (!onAct || !selected) return
    setBusy(true)
    setFormError('')
    let untilSec = null
    if (selected.needsUntil) {
      untilSec = spanToSend(spanRef.current)
      if (untilSec == null) {
        setFormError('Укажите срок больше нуля и не дольше 366 дней')
        setBusy(false)
        return
      }
    }
    try {
      await onAct({
        userId: String(userId),
        action: selected.id,
        untilSec,
        reason: reason.trim(),
      })
      setReason('')
      const data = await reload()
      setFreshId(data?.items?.[0]?.id ?? null)
      const body = document.querySelector('.focus-sheet-body')
      if (body) body.scrollTop = 0
    } catch (err) {
      setFormError(err.message || 'Наказание не ушло')
    } finally {
      setBusy(false)
    }
  }

  async function lift(event, actId) {
    event.preventDefault()
    if (!onAct || !liftReason.trim()) {
      setFormError('Нужна причина')
      return
    }
    setBusy(true)
    setFormError('')
    try {
      await onAct({
        userId: String(userId),
        action: actId,
        untilSec: null,
        reason: liftReason.trim(),
      })
      setLiftId(null)
      setLiftReason('')
      const data = await reload()
      setFreshId(data?.items?.[0]?.id ?? null)
    } catch (err) {
      setFormError(err.message || 'Снятие не ушло')
    } finally {
      setBusy(false)
    }
  }

  const name = report?.name || (warns?.name) || 'Человек'
  const username = report?.username ? `@${String(report.username).replace(/^@/, '')}` : `#${userId}`
  const items = report?.available === false ? [] : (report?.items || [])

  const form = offered.all.length > 0 ? (
    <form className="person-issue" onSubmit={submit}>
      <div className="person-issue-scroll">
      <p className="person-issue-title">Ещё наказание</p>
      {offered.wide.length > 0 ? (
        <>
          <ChipRow items={offered.local} selectedId={selected?.id} onPick={setAction} label="В этом чате" />
          <ChipRow items={offered.wide} selectedId={selected?.id} onPick={setAction} label="Шире этого чата" />
        </>
      ) : (
        <div className="person-acts" role="group" aria-label="Какое наказание выдать">
          {offered.local.map((item) => (
            <button
              key={item.id}
              type="button"
              className={selected?.id === item.id ? 'is-on' : ''}
              aria-pressed={selected?.id === item.id}
              onClick={() => setAction(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      {scopeHint && (
        <p className="person-scope" key={selected?.id}>{scopeHint}</p>
      )}
      {selected?.needsUntil && (
        <SpanClock
          seconds={spanSec}
          onChange={(next) => {
            spanRef.current = next
            setSpanSec(next)
          }}
        />
      )}
      <label>
        Причина
        <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="что человек сделал" required />
      </label>
      {formError && <p className="realm-alert" role="alert">{formError}</p>}
      </div>
      <button type="submit" className="sec-btn" disabled={busy || !selected}>
        {busy ? 'Запись…' : issueVerb(selected, spanSec)}
      </button>
    </form>
  ) : (
    <p className="person-read">Эта должность не выдаёт наказания. Здесь только то, что уже было.</p>
  )

  return (
    <FocusWindow
      title={loading && !report ? 'Наказания' : name}
      subtitle={warns ? `${username} · предупреждений ${warns.warns} из 3` : username}
      onClose={onClose}
      footer={form}
    >
      {error && (
        <p className="realm-alert" role="alert">
          {error}
          <button type="button" className="gate-text" onClick={() => {
            setLoading(true)
            setError('')
            fetchPersonHistory(chatId, userId)
              .then(setReport)
              .catch((err) => setError(err.message || 'История не открылась'))
              .finally(() => setLoading(false))
          }}
          >
            Повторить
          </button>
        </p>
      )}
      {loading && !report && <p className="person-read">Открываем наказания…</p>}
      {report?.available === false && (
        <p className="person-read">История не открылась. Нулей вместо записей здесь нет.</p>
      )}
      {report && report.available !== false && items.length === 0 && !loading && (
        <p className="person-read">Раньше наказаний не было. Первое можно выдать снизу.</p>
      )}
      {items.length > 0 && (
        <ol className="person-deeds">
          {items.map((row, index) => {
            const liftAction = liftOf(row.action)
            const canLift = liftAction && spanOf(row) === 'Этот чат' && actions.some((item) => item.id === liftAction.id)
            const open = liftId === row.id
            return (
              <li
                key={row.id}
                className={`person-deed${Number(freshId) === Number(row.id) ? ' is-arrive' : ''}`}
                style={{ animationDelay: `${Math.min(index, 6) * 40}ms` }}
              >
                <div className="person-deed-top">
                  <strong>{labelOf(row.action)}</strong>
                  <time dateTime={row.at || undefined}>{when(row.at)}</time>
                </div>
                <p>{row.reason || 'Причина не указана'}</p>
                <p className="person-deed-meta">
                  {row.admin || 'Кто выдал, не записан'}
                  {' · '}
                  {spanOf(row)}
                  {held(row) ? ` · ${held(row)}` : ''}
                </p>
                {row.hasProof && row.proofMediaId && (
                  <PhotoLook fileId={row.proofMediaId} alt="Фото к наказанию" />
                )}
                {canLift && (
                  open ? (
                    <form className="person-lift" onSubmit={(event) => lift(event, liftAction.id)}>
                      <label>
                        Причина снятия
                        <input
                          value={liftReason}
                          onChange={(event) => setLiftReason(event.target.value)}
                          placeholder="зачем снимаете"
                          required
                        />
                      </label>
                      <div className="person-lift-row">
                        <button type="submit" className="sec-btn" disabled={busy}>{busy ? 'Снимаем…' : liftAction.label}</button>
                        <button type="button" className="sec-btn sec-btn-ghost" onClick={() => { setLiftId(null); setLiftReason('') }}>Отмена</button>
                      </div>
                    </form>
                  ) : (
                    <button
                      type="button"
                      className="sec-btn person-lift-open"
                      onClick={() => {
                        if (/разбан|разблок/i.test(liftAction.label)) playMeme('wont')
                        setLiftId(row.id)
                        setLiftReason('')
                      }}
                    >
                      {liftAction.label}
                    </button>
                  )
                )}
              </li>
            )
          })}
        </ol>
      )}
      {report?.clipped && (
        <p className="person-read">Показаны последние 200. Более старые в этот список не влезли.</p>
      )}
    </FocusWindow>
  )
}
