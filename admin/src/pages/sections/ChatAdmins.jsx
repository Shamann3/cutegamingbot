import { useCallback, useEffect, useState } from 'react'
import { actChatAdmin, fetchChatAdmins } from '../../lib/adminClient'
import '../../styles/chat-admins.css'

const ACTION_LABEL = {
  chat_admin_demote: 'Снял админку',
  chat_admin_restrict: 'Ограничил права',
}

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

export default function ChatAdmins({ chatId }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    if (!chatId) return
    setError('')
    try {
      setBoard(await fetchChatAdmins(chatId))
    } catch (err) {
      setError(err?.message || 'Не удалось открыть администраторов')
    }
  }, [chatId])

  useEffect(() => { load() }, [load])

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

  if (!board && !error) {
    return <p className="realm-copy">Собираем администраторов группы…</p>
  }

  const admins = board?.admins || []
  const history = board?.history || []
  const canAct = Boolean(board?.canAct && board?.botCanPromote)
  const selfId = Number(board?.selfId || 0)

  return (
    <section className="chat-admins">
      <h2 className="realm-h">Администраторы группы</h2>
      <p className="realm-copy">
        Все, кого Telegram считает администраторами этого чата.
        Снятие убирает админку. Ограничение оставляет человека администратором, но без удаления, банов и назначения.
        Кто и что сделал — в журнале ниже.
      </p>
      {board?.error && <p className="chat-admins-warn">{board.error}</p>}
      {error && <p className="chat-admins-warn">{error}</p>}
      {note && <p className="chat-admins-note">{note}</p>}
      {board && !board.botCanPromote && !board.error && (
        <p className="chat-admins-warn">Боту нужно право назначать администраторов, иначе кнопки не сработают.</p>
      )}

      <ul className="chat-admins-list">
        {admins.map((person) => {
          const locked = person.status === 'creator' || person.isSelfBot || person.userId === selfId
          return (
            <li key={person.userId} className="chat-admins-card">
              <div>
                <strong>{person.name}</strong>
                <span className="chat-admins-status">{statusLabel(person.status)}</span>
                {person.title ? <span className="chat-admins-title">{person.title}</span> : null}
              </div>
              <p>
                {person.username ? `@${person.username} · ` : ''}
                <code>{person.userId}</code>
              </p>
              <p className="chat-admins-powers">{powers(person)}</p>
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
    </section>
  )
}
