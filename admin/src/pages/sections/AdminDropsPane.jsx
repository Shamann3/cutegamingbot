import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { decideAdminDrop, fetchAdminDrops } from '../../lib/adminClient'
import '../../styles/group-admins-desk.css'

const STATUS = {
  pending: 'Ждёт решения',
  approved: 'Принята',
  rejected: 'Отклонена',
}

function when(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AdminDropsPane() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)
  const reduce = useReducedMotion()

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

  const pending = useMemo(
    () => items.filter((item) => item.status === 'pending').length,
    [items],
  )

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

  const motionSafe = reduce
    ? {}
    : {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -6 },
        transition: { type: 'spring', stiffness: 380, damping: 32 },
      }

  return (
    <section className="gad admin-drops-desk">
      <header className="gad-hero">
        <span className="gad-hero-glow" aria-hidden="true" />
        <div className="gad-hero-copy">
          <p className="gad-kicker">Администраторы · снятия</p>
          <h3>Заявки на снятие</h3>
          <p>
            Принять — человек становится обычным участником группы.
            Отклонить — должность остаётся. Те же кнопки приходят в личные сообщения.
          </p>
          <div className="gad-stats">
            <span>
              Ждут
              {' '}
              <strong>{pending}</strong>
            </span>
            <span>
              Всего
              {' '}
              <strong>{items.length}</strong>
            </span>
          </div>
        </div>
      </header>

      <div className="gad-toolbar">
        <button type="button" className="gad-btn" onClick={load} disabled={loading}>
          {loading ? 'Обновляем…' : 'Обновить'}
        </button>
      </div>

      <AnimatePresence mode="popLayout">
        {error && (
          <motion.p className="gad-error" role="alert" key="err" {...motionSafe}>
            {error}
          </motion.p>
        )}
        {notice && (
          <motion.p className="gad-note" role="status" key="ok" {...motionSafe}>
            {notice}
          </motion.p>
        )}
      </AnimatePresence>

      {loading && items.length === 0 && (
        <p className="gad-empty">Собираем заявки на снятие…</p>
      )}
      {!loading && items.length === 0 && (
        <p className="gad-empty">Заявок на снятие нет</p>
      )}

      <ul className="gad-list admin-drops-list">
        <AnimatePresence initial={false}>
          {items.map((item, index) => {
            const waiting = item.status === 'pending'
            return (
              <motion.li
                key={item.id}
                className={`gad-card admin-drop-card${waiting ? ' is-waiting' : ''}`}
                layout={!reduce}
                initial={reduce ? false : { opacity: 0, y: 14, scale: 0.985 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reduce ? undefined : { opacity: 0, y: -8, scale: 0.98 }}
                transition={{
                  type: 'spring',
                  stiffness: 360,
                  damping: 30,
                  delay: reduce ? 0 : Math.min(index, 6) * 0.04,
                }}
              >
                <div className="gad-card-head">
                  <strong>
                    {item.name || 'Без имени'}
                    {item.username ? ` · @${item.username}` : ''}
                  </strong>
                  <span className={`admin-drop-status is-${item.status || 'pending'}`}>
                    {STATUS[item.status] || item.status}
                  </span>
                </div>
                <p className="gad-meta admin-drop-meta">
                  <span className="admin-drop-chip">{item.group || 'Группа'}</span>
                  <span className="admin-drop-chip">просит {item.actorName || '—'}</span>
                  {item.at ? <span className="admin-drop-chip">{when(item.at)}</span> : null}
                  <span className="admin-drop-chip">id {item.userId}</span>
                </p>
                {waiting && (
                  <div className="gad-actions admin-drop-actions">
                    <button
                      type="button"
                      className="gad-btn gad-btn-primary"
                      disabled={busyId === item.id}
                      onClick={() => decide(item, true)}
                    >
                      {busyId === item.id ? '…' : 'Принять снятие'}
                    </button>
                    <button
                      type="button"
                      className="gad-btn gad-btn-danger"
                      disabled={busyId === item.id}
                      onClick={() => decide(item, false)}
                    >
                      Отклонить
                    </button>
                  </div>
                )}
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
    </section>
  )
}
