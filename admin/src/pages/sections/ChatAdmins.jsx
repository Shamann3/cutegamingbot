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
  const canAct = Boolean(board?.canAct && board?.botCanPromote)
  const selfId = Number(board?.selfId || 0)
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
            Цифры — только эта группа, как строка активности в профиле.
            Снять админку и урезать права можно здесь.
            Бан на весь проект и создателя группы решает создатель проекта @JerichoCute.
          </p>
          {board?.error && <p className="chat-admins-warn">{board.error}</p>}
          {board && !board.botCanPromote && !board.error && (
            <p className="chat-admins-warn">Боту нужно право назначать администраторов, иначе кнопки не сработают.</p>
          )}

          <ul className="chat-admins-list">
            {admins.map((person, index) => {
              const locked = person.status === 'creator' || person.isSelfBot || person.userId === selfId
              const stats = person.stats
              return (
                <li key={person.userId} className="chat-admins-card" style={{ animationDelay: `${index * 40}ms` }}>
                  <div className="chat-admins-head">
                    <strong>{person.name}</strong>
                    <span className="chat-admins-status">{statusLabel(person.status)}</span>
                    {person.title ? <span className="chat-admins-title">{person.title}</span> : null}
                  </div>
                  <p>
                    {person.username ? `@${person.username} · ` : ''}
                    <code>{person.userId}</code>
                  </p>
                  <p className="chat-admins-powers">{powers(person)}</p>
                  {!person.isBot && stats ? (
                    <div className="chat-admins-analytics">
                      <p className="chat-admins-last">Последняя активность: {stats.last}</p>
                      <div className="chat-admins-meters">
                        {METERS.map(([key, label]) => {
                          const value = Number(stats[key]) || 0
                          const width = key === 'month' ? Math.round((value / monthPeak) * 100) : null
                          return (
                            <div key={key}>
                              <span>{label}</span>
                              <strong>{count(value)}</strong>
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
                      <button type="button" className="is-danger" onClick={() => setPending({ ...person, action: 'demote' })}>
                        Снять
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
                  ? `Снять админку: ${pending.name} станет обычным участником.`
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
