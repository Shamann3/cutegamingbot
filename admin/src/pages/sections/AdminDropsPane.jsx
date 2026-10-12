import { useCallback, useEffect, useState } from 'react'
import { decideAdminDrop, fetchAdminDrops } from '../../lib/adminClient'

const STATUS = {
  pending: 'Ждёт решения',
  approved: 'Принята',
  rejected: 'Отклонена',
}

function when(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export default function AdminDropsPane() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchAdminDrops()
      setItems(Array.isArray(data?.items) ? data.items : [])
    } catch (err) {
      setError(err?.message || 'Заявки на снятие не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function decide(item, approve) {
    if (busyId) return
    setBusyId(item.id)
    setError('')
    setNotice('')
    try {
      const data = await decideAdminDrop(item.id, approve)
      setNotice(data?.toast || (approve ? 'Админка снята' : 'Заявка отклонена'))
      await load()
    } catch (err) {
      setError(err?.message || 'Решение не сохранилось')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="admin-drops">
      <h3 className="realm-h">Снятия администраторов</h3>
      <p className="realm-copy">
        Заявки из вкладки «Админы» группы. Принять — человек становится обычным участником.
        Отклонить — должность остаётся. Те же кнопки приходят в личные сообщения.
      </p>
      {error && <p className="chat-admins-warn">{error}</p>}
      {notice && <p className="chat-admins-note">{notice}</p>}
      {loading && <p className="realm-copy">Собираем заявки…</p>}
      {!loading && items.length === 0 && <p className="realm-copy">Заявок на снятие нет.</p>}
      <ul className="realm-list">
        {items.map((item) => {
          const waiting = item.status === 'pending'
          return (
            <li key={item.id} className="realm-row">
              <strong>{item.name}{item.username ? ` · @${item.username}` : ''}</strong>
              <span>{item.group} · {STATUS[item.status] || item.status} · просит {item.actorName}</span>
              <span>{when(item.at)} · id {item.userId}</span>
              {waiting && (
                <span>
                  <button type="button" disabled={busyId === item.id} onClick={() => decide(item, true)}>Принять</button>
                  <button type="button" disabled={busyId === item.id} onClick={() => decide(item, false)}>Отклонить</button>
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
