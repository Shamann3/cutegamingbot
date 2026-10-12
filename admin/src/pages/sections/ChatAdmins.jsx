import { useCallback, useEffect, useState } from 'react'
import {
  actChatAdmin,
  adviseChatApplication,
  fetchChatAdmins,
  fetchChatApplications,
} from '../../lib/adminClient'
import '../../styles/chat-admins.css'

const ACTION_LABEL = {
  chat_admin_demote: 'Снял админку',
  chat_admin_restrict: 'Ограничил права',
  chat_admin_drop_ask: 'Попросил снять',
  chat_admin_drop_no: 'Отклонил снятие',
  chat_admin_unregistered: 'Снял незарегистрированного',
}

function personLine(person) {
  const name = person.name || (person.username ? `@${person.username}` : `ID ${person.userId}`)
  return person.username && !name.startsWith('@') ? `${name} (@${person.username})` : name
}

const METERS = [
  ['day', 'Сегодня'],
  ['week', '7 дней'],
  ['month', 'Месяц'],
  ['total', 'Всё время'],
]

const DEED_LABEL = [
  ['mute', 'Муты'],
  ['ban', 'Баны'],
  ['kick', 'Кики'],
  ['warn', 'Варны'],
]

function statusLabel(status) {
  if (status === 'creator') return 'Создатель'
  if (status === 'administrator') return 'Администратор'
  return 'Админ'
}

function sameText(left, right) {
  return String(left || '').trim().toLowerCase() === String(right || '').trim().toLowerCase()
}

function personHeading(person) {
  const id = String(person.userId)
  const raw = String(person.name || '').trim()
  const nameIsId = !raw || raw === id || raw === `ID ${id}`
  const status = statusLabel(person.status)
  const title = String(person.title || '').trim()
  const role = title && !sameText(title, status) ? `${status} · ${title}` : status
  return {
    name: nameIsId ? (person.username ? `@${person.username}` : id) : raw,
    meta: [
      !nameIsId && person.username ? `@${person.username}` : '',
      nameIsId ? '' : id,
    ].filter(Boolean).join(' · '),
    role,
  }
}

function powers(person) {
  if (person.status === 'creator') return 'Полные права группы'
  const parts = []
  if (person.canDelete) parts.push('удаляет')
  if (person.canRestrict) parts.push('банит')
  if (person.canPromote) parts.push('назначает')
  return parts.length ? parts.join(' · ') : 'без банов и удаления'
}

function when(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function count(value) {
  return new Intl.NumberFormat('ru-RU').format(Number(value) || 0)
}

function verdictLabel(verdict) {
  return verdict === 'fit' ? 'Подходит' : 'Не подходит'
}

export default function ChatAdmins({ chatId }) {
  const [tab, setTab] = useState('people')
  const [board, setBoard] = useState(null)
  const [apps, setApps] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [draft, setDraft] = useState(null)
  const [explain, setExplain] = useState('')

  const loadPeople = useCallback(async () => {
    if (!chatId) return
    setError('')
    try {
      setBoard(await fetchChatAdmins(chatId))
    } catch (err) {
      setError(err?.message || 'Не удалось открыть администраторов')
    }
  }, [chatId])

  const loadApps = useCallback(async () => {
    if (!chatId) return
    setError('')
    try {
      const data = await fetchChatApplications(chatId)
      setApps(Array.isArray(data?.items) ? data.items : [])
    } catch (err) {
      setError(err?.message || 'Заявки этой группы не открылись')
    }
  }, [chatId])

  useEffect(() => { loadPeople() }, [loadPeople])
  useEffect(() => {
    if (tab === 'apps' && apps === null) loadApps()
  }, [tab, apps, loadApps])

  async function commit() {
    if (!pending || busy) return
    setBusy(true)
    setError('')
    try {
      const next = await actChatAdmin(chatId, pending.userId, pending.action)
      setBoard(next)
      setNote(next.note || '')
      setPending(null)
    } catch (err) {
      setError(err?.message || 'Telegram не выполнил действие')
    } finally {
      setBusy(false)
    }
  }

  async function sendAdvice(item) {
    if (!draft || draft.id !== item.id || busy) return
    setBusy(true)
    setError('')
    try {
      await adviseChatApplication(chatId, item.id, draft.verdict, explain.trim())
      setDraft(null)
      setExplain('')
      setNote(draft.verdict === 'fit' ? 'Рекомендация отправлена: подходит' : 'Рекомендация отправлена: не подходит')
      await loadApps()
    } catch (err) {
      setError(err?.message || 'Рекомендация не сохранилась')
    } finally {
      setBusy(false)
    }
  }

  if (!board && !error) {
    return <p className="realm-copy">Собираем администраторов группы…</p>
  }

  const admins = board?.admins || []
  const history = board?.history || []
  const canAct = Boolean(board?.canAct)
  const creator = Boolean(board?.creator)
  const selfId = Number(board?.selfId || 0)
  const dropped = board?.dropped || []
  const stuck = board?.stuck || []
  const monthPeak = Math.max(1, ...admins.map((person) => Number(person.stats?.month) || 0))

  return (
    <section className="chat-admins">
      <div className="chat-admins-tabs" role="tablist" aria-label="Админы группы">
        <button type="button" role="tab" aria-selected={tab === 'people'} onClick={() => setTab('people')}>
          Состав
        </button>
        <button type="button" role="tab" aria-selected={tab === 'apps'} onClick={() => setTab('apps')}>
          Заявки
        </button>
      </div>

      {error && <p className="chat-admins-warn">{error}</p>}
      {note && <p className="chat-admins-note">{note}</p>}

      {tab === 'people' && (
        <div className="chat-admins-pane">
          <h2 className="realm-h">Администраторы группы</h2>
          <p className="realm-copy">
            Здесь только администраторы с должностью в этой группе. Сотрудники проекта не показаны.
            Кто администратор в Telegram, но не в системе, снимается сам.
            Ограничить права можно сразу. Снятие должности уходит создателю @JerichoCute, если это делаете не вы.
          </p>
          {board?.error && <p className="chat-admins-warn">{board.error}</p>}
          {dropped.length > 0 && (
            <p className="chat-admins-note">
              Снял админку тем, кого нет в системе: {dropped.map(personLine).join(', ')}.
            </p>
          )}
          {stuck.length > 0 && (
            <p className="chat-admins-warn">
              Не удалось снять тех, кого нет в системе: {stuck.map((person) => `${personLine(person)} — ${person.error}`).join('; ')}.
            </p>
          )}
          {board && !board.botCanPromote && !board.error && (
            <p className="chat-admins-warn">
              Если снятие не пройдёт, включите боту в этой группе «Добавление администраторов».
            </p>
          )}

          <ul className="chat-admins-list">
            {admins.map((person, index) => {
              const locked = person.status === 'creator' || person.isSelfBot || person.userId === selfId
              const stats = person.stats
              const heading = personHeading(person)
              return (
                <li key={person.userId} className="chat-admins-card" style={{ animationDelay: `${index * 40}ms` }}>
                  <div className="chat-admins-head">
                    <strong>{heading.name}</strong>
                    <span className="chat-admins-status">{heading.role}</span>
                  </div>
                  {heading.meta ? <p>{heading.meta}</p> : null}
                  <p className="chat-admins-powers">{powers(person)}</p>
                  {!person.isBot && stats ? (
                    <div className="chat-admins-analytics">
                      <p className="chat-admins-last">Последняя активность: {stats.last}</p>
                      <div className="chat-admins-meters">
                        {METERS.map(([key, label]) => {
                          const value = Number(stats[key]) || 0
                          const width = key === 'month' ? Math.round((value / monthPeak) * 100) : null
                          return (
                            <div className="chat-admins-meter" key={key}>
                              <strong>{count(value)}</strong>
                              <span>{label}</span>
                              {width !== null && (
                                <i aria-hidden="true"><b style={{ width: `${width}%` }} /></i>
                              )}
                            </div>
                          )
                        })}
                      </div>
                      {person.deeds && (
                        <p className="chat-admins-deeds">
                          За 30 дней: {DEED_LABEL.map(([key, label]) => `${label} ${count(person.deeds[key])}`).join(' · ')}
                        </p>
                      )}
                    </div>
                  ) : !person.isBot ? (
                    <p className="chat-admins-powers">Активность этой группы сейчас не посчиталась.</p>
                  ) : null}
                  {canAct && !locked && (
                    <div className="chat-admins-actions">
                      <button type="button" onClick={() => setPending({ ...person, action: 'restrict' })}>
                        Ограничить
                      </button>
                      <button
                        type="button"
                        className="is-danger"
                        disabled={Boolean(person.dropPending) && !creator}
                        onClick={() => setPending({ ...person, action: 'demote' })}
                      >
                        {person.dropPending && !creator ? 'Заявка у создателя' : 'Снять'}
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
          {board && admins.length === 0 && !board.error && (
            <p className="realm-copy">В этой группе администраторов не видно.</p>
          )}

          {pending && (
            <div className="chat-admins-confirm" role="dialog" aria-label="Подтверждение">
              <p>
                {pending.action === 'demote'
                  ? (creator
                    ? `Снять админку: ${pending.name} станет обычным участником.`
                    : `Заявка создателю @JerichoCute: снять ${pending.name}. Он примет или отклонит в личных сообщениях.`)
                  : `Ограничить права: ${pending.name} останется администратором, но без удаления, банов и назначения.`}
              </p>
              <div>
                <button type="button" disabled={busy} onClick={() => setPending(null)}>Назад</button>
                <button type="button" className="is-danger" disabled={busy} onClick={commit}>
                  {busy ? 'Записываем…' : 'Подтвердить'}
                </button>
              </div>
            </div>
          )}

          <h3 className="realm-h">Журнал</h3>
          {history.length === 0 ? (
            <p className="realm-copy">Пока никто отсюда администраторов не снимал и не ограничивал.</p>
          ) : (
            <ol className="chat-admins-log">
              {history.map((row) => (
                <li key={row.id}>
                  <span>{when(row.at)}</span>
                  <strong>{row.actorName}</strong>
                  <em>{ACTION_LABEL[row.action] || row.action}</em>
                  <p>{row.detail}</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {tab === 'apps' && (
        <div className="chat-admins-pane">
          <h2 className="realm-h">Заявки на должность</h2>
          <p className="realm-copy">
            Здесь только эта группа. Можно отметить «Подходит» или «Не подходит» и дописать пояснение.
            Принять заявку может создатель проекта, в том числе без вашей отметки.
            Если случай серьёзный — напишите @JerichoCute.
          </p>
          {apps === null && <p className="realm-copy">Собираем заявки…</p>}
          {apps && apps.length === 0 && <p className="realm-copy">Заявок в эту группу нет.</p>}
          <ul className="chat-admins-list">
            {(apps || []).map((item) => {
              const open = draft?.id === item.id
              const pendingApp = (item.status || 'pending') === 'pending'
              return (
                <li key={item.id} className="chat-admins-card">
                  <div className="chat-admins-head">
                    <strong>{item.name || `ID ${item.userId}`}</strong>
                    <span className="chat-admins-status">{item.position}</span>
                  </div>
                  <p>
                    {item.username ? `@${item.username} · ` : ''}
                    <code>{item.userId}</code>
                  </p>
                  {item.body ? <p className="chat-admins-powers">{item.body}</p> : null}
                  {(item.advice || []).map((advice) => (
                    <p key={advice.actorId} className="chat-admins-advice">
                      Рекомендация от {advice.name} — {verdictLabel(advice.verdict)}
                      {advice.note ? `. ${advice.note}` : ''}
                    </p>
                  ))}
                  {pendingApp && (
                    <div className="chat-admins-actions">
                      <button
                        type="button"
                        className={open && draft.verdict === 'fit' ? 'is-on' : ''}
                        onClick={() => { setDraft({ id: item.id, verdict: 'fit' }); setExplain(''); setError('') }}
                      >
                        Подходит
                      </button>
                      <button
                        type="button"
                        className={open && draft.verdict === 'unfit' ? 'is-on' : ''}
                        onClick={() => { setDraft({ id: item.id, verdict: 'unfit' }); setExplain(''); setError('') }}
                      >
                        Не подходит
                      </button>
                    </div>
                  )}
                  {open && (
                    <form className="chat-admins-advice-form" onSubmit={(event) => { event.preventDefault(); sendAdvice(item) }}>
                      <label>
                        Пояснение, если нужно
                        <textarea value={explain} maxLength={400} rows={3} onChange={(event) => setExplain(event.target.value)} />
                      </label>
                      <button type="submit" disabled={busy}>
                        {busy ? 'Отправляем…' : 'Отправить рекомендацию'}
                      </button>
                    </form>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
