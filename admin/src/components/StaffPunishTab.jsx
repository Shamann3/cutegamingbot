import { useEffect, useRef, useState } from 'react'
import { staffPunish } from '../lib/adminClient'
import { notifyAdmin } from '../lib/notify'
import { spanToSend } from '../lib/spanClock'
import { isLift, punishProblem, punishReceipt, punishShelves, punishVerb } from '../lib/staffPunish'
import SpanClock from './SpanClock'

export default function StaffPunishTab({ userId, actorId = null, options = null, loadError = '', onRetry }) {
  const actions = options?.actions || []
  const groups = options?.groups || []
  const [actionId, setActionId] = useState(actions[0]?.id || '')
  const [chatId, setChatId] = useState(groups[0] ? String(groups[0].chatId) : '')
  const spanRef = useRef(3600)
  const [spanSec, setSpanSec] = useState(3600)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')

  useEffect(() => {
    if (actions.length && !actions.some((item) => item.id === actionId)) setActionId(actions[0].id)
  }, [actions, actionId])

  useEffect(() => {
    if (groups.length && !groups.some((item) => String(item.chatId) === chatId)) setChatId(String(groups[0].chatId))
  }, [groups, chatId])

  useEffect(() => {
    setReason('')
    setError('')
    setDone('')
  }, [userId])

  if (loadError) {
    return (
      <p className="panel-shelf-error" role="alert">
        {loadError}
        {' '}
        <button type="button" className="panel-users-btn" onClick={onRetry}>Повторить</button>
      </p>
    )
  }
  if (!options) return <p className="panel-shelf-muted">Проверяем права…</p>
  if (!actions.length) return <p className="panel-shelf-muted">{options.why || 'Наказаний из панели у вашей должности нет.'}</p>
  if (!groups.length) {
    return <p className="panel-shelf-muted">Официальных групп пока нет. Их отмечает создатель проекта.</p>
  }

  const shelves = punishShelves(actions)
  const selected = actions.find((item) => item.id === actionId) || actions[0]
  const lift = isLift(selected.id)

  async function submit(event) {
    event.preventDefault()
    if (options.preview) {
      setError('Это просмотр. Наказание не уходит.')
      return
    }
    const problem = punishProblem({
      action: selected,
      chatId,
      spanSec: spanRef.current,
      reason,
      actorId,
      targetId: userId,
    })
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError('')
    setDone('')
    try {
      const result = await staffPunish({
        chatId,
        userId,
        action: selected.id,
        untilSec: selected.needsUntil ? spanToSend(spanRef.current) : null,
        reason: reason.trim(),
      })
      const line = punishReceipt(result)
      setDone(line)
      setReason('')
      notifyAdmin(`Готово: ${line}`)
    } catch (err) {
      setError(err.message || 'Наказание не ушло')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="staff-punish" onSubmit={submit} noValidate>
      <div>
        <h4 className="pu-section-title">Наказать</h4>
        <p className="panel-shelf-muted">
          {options.preview
            ? 'Так вкладку видит эта должность. В тестовом режиме наказание не уходит.'
            : 'Здесь только то, что разрешает ваша должность. Сервер проверяет каждое наказание.'}
        </p>
      </div>

      <label className="pu-field">
        <span className="pu-field-label">Группа</span>
        <select
          className="panel-users-input pu-field-input"
          value={chatId}
          onChange={(event) => setChatId(event.target.value)}
        >
          {groups.map((group) => (
            <option key={group.chatId} value={String(group.chatId)}>{group.title}</option>
          ))}
        </select>
      </label>

      {shelves.map((shelf) => (
        <div key={shelf.id} className="person-issue-block">
          <p className="person-issue-title">{shelf.title}</p>
          <div className="person-acts" role="group" aria-label={shelf.title}>
            {shelf.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={selected.id === item.id ? 'is-on' : ''}
                aria-pressed={selected.id === item.id}
                onClick={() => {
                  setActionId(item.id)
                  setError('')
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      {selected.hint && <p className="person-scope" key={selected.id}>{selected.hint}</p>}

      {selected.needsUntil && (
        <SpanClock
          seconds={spanSec}
          onChange={(next) => {
            spanRef.current = next
            setSpanSec(next)
          }}
        />
      )}

      <label className="pu-field">
        <span className="pu-field-label">Причина</span>
        <input
          className="panel-users-input pu-field-input"
          value={reason}
          maxLength={200}
          onChange={(event) => setReason(event.target.value)}
          placeholder={lift ? 'зачем снимаете' : 'что человек сделал'}
        />
      </label>

      {error && <p className="panel-shelf-error" role="alert">{error}</p>}
      {done && <p className="staff-punish-done" role="status">Готово: {done}</p>}

      <button type="submit" className="panel-users-btn panel-users-btn-danger" disabled={busy || options.preview}>
        {options.preview ? 'Тестовый режим' : busy ? 'Отправляем…' : punishVerb(selected, spanSec)}
      </button>
    </form>
  )
}
