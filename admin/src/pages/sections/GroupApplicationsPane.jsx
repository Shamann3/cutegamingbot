import { useCallback, useEffect, useState } from 'react'
import { decideGroupApplication, fetchGroupApplications } from '../../lib/adminClient'
import { applicationPerson } from '../../lib/applicationPerson'
import { CopyableId, CopyableUsername } from '../../components/Copyable'

function when(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ''
  }
}

const APP_STATUS = {
  pending: 'На рассмотрении',
  rejected: 'Отклонена',
  approved: 'Принята',
}

export default function GroupApplicationsPane({ onOpenUser = null }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [keyOnce, setKeyOnce] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [rejectId, setRejectId] = useState(null)
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchGroupApplications()
      setItems(Array.isArray(data?.items) ? data.items : [])
    } catch (err) {
      setError(err.message || 'Заявки администраторов не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const approve = async (item) => {
    setBusyId(item.id)
    setError('')
    setNotice('')
    setKeyOnce('')
    try {
      const data = await decideGroupApplication({
        application_id: item.id,
        approve: true,
        note: '',
      })
      setItems((list) => list.filter((row) => row.id !== item.id))
      setKeyOnce(data?.entryKey || '')
      setNotice(data?.entryKey
        ? 'Заявка одобрена. Ключ ушёл человеку в бота. Здесь он тоже показан — передайте его, если сообщение не дошло.'
        : 'Заявка одобрена.')
    } catch (err) {
      setError(err.message || 'Одобрить не удалось')
    } finally {
      setBusyId(null)
    }
  }

  const reject = async (item) => {
    const reason = note.trim()
    if (reason.length < 2) {
      setError('Отказ сохраняется только с причиной')
      return
    }
    setBusyId(item.id)
    setError('')
    setNotice('')
    try {
      await decideGroupApplication({
        application_id: item.id,
        approve: false,
        note: reason,
      })
      setItems((list) => list.filter((row) => row.id !== item.id))
      setRejectId(null)
      setNote('')
      setNotice('Заявка отклонена')
    } catch (err) {
      setError(err.message || 'Отказ не сохранился')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="sec-tab-body staff-apps staff-apps-group">
      <p className="staff-hint">
        Здесь все заявки в кабинет. Сначала те, что ждут решения. Если человек уже на должности, заявка нужна только для ключа. «Открыть в Игроках» показывает его карточку. Заявка не делает его сотрудником проекта.
      </p>
      {error && <p className="sec-error" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}
      {keyOnce && (
        <p className="realm-alert" data-copyable="1">
          Личный ключ, один показ: <code>{keyOnce}</code>
        </p>
      )}
      <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={load} disabled={loading}>
        {loading ? 'Сверяем…' : 'Обновить'}
      </button>
      {loading && items.length === 0 && <p className="sec-loading">Загрузка заявок…</p>}
      {!loading && items.length === 0 && !error && (
        <p className="sec-empty">Заявок в панель администратора нет.</p>
      )}
      <ul className="staff-app-list">
        {items.map((item) => {
          const person = applicationPerson(item)
          return (
          <li key={item.id} className="staff-app-card">
            <div className="staff-app-head">
              <strong>{person.title}</strong>
              <span>{item.group}</span>
            </div>
            <p className="staff-app-meta">
              {person.username ? <><CopyableUsername value={person.username} />{' · '}</> : null}
              {item.position} · ранг {item.rank} · {APP_STATUS[item.status] || item.status || 'На рассмотрении'}{item.at ? ` · ${when(item.at)}` : ''}
            </p>
            {item.alreadySeated && (item.status || 'pending') === 'pending' && (
              <p className="staff-app-meta">Уже на должности. Заявка нужна, чтобы выдать ключ.</p>
            )}
            {item.note && (item.status || 'pending') !== 'pending' && (
              <p className="staff-app-meta">{item.note}</p>
            )}
            <p className="staff-app-meta"><CopyableId value={item.userId} label="id игрока" /></p>
            <p className="staff-app-body">{item.body}</p>
            <div className="staff-app-actions">
              {onOpenUser && (
                <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => onOpenUser(item.userId)}>
                  Открыть в Игроках
                </button>
              )}
              {(item.status || 'pending') === 'pending' && (
                <>
                  <button type="button" className="sec-btn sec-btn-sm" disabled={busyId === item.id} onClick={() => approve(item)}>
                    {busyId === item.id ? '…' : 'Одобрить'}
                  </button>
                  <button
                    type="button"
                    className="sec-btn sec-btn-ghost sec-btn-sm"
                    disabled={busyId === item.id}
                    onClick={() => { setRejectId(item.id); setNote(''); setError('') }}
                  >
                    Отказать
                  </button>
                </>
              )}
            </div>
            {rejectId === item.id && (item.status || 'pending') === 'pending' && (
              <form className="staff-app-reject" onSubmit={(event) => { event.preventDefault(); reject(item) }}>
                <label>
                  Причина отказа
                  <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} />
                </label>
                <button type="submit" className="sec-btn sec-btn-danger sec-btn-sm" disabled={busyId === item.id || note.trim().length < 2}>
                  Сохранить отказ
                </button>
              </form>
            )}
          </li>
          )
        })}
      </ul>
    </div>
  )
}
