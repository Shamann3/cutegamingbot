import { useCallback, useEffect, useMemo, useState } from 'react'
import ApproveSeat from '../../components/ApproveSeat'
import { CopyableId, CopyableUsername } from '../../components/Copyable'
import {
  appointGroupAdmin,
  decideAdminDrop,
  decideGroupApplication,
  dismissGroupAdmin,
  fetchAdminDrops,
  fetchGroupApplications,
  fetchRightsBoard,
} from '../../lib/adminClient'
import { applicationPerson } from '../../lib/applicationPerson'
import { adminSeatChoices } from '../../lib/seatChoice'
import '../../styles/group-admins-desk.css'

const SEGMENTS = [
  { id: 'roster', label: 'Список' },
  { id: 'apps', label: 'Заявки' },
  { id: 'drops', label: 'Снятия' },
  { id: 'appoint', label: 'Назначить' },
]

const APP_STATUS = {
  pending: 'На рассмотрении',
  rejected: 'Отклонена',
  approved: 'Принята',
}

const DROP_STATUS = {
  pending: 'Ждёт решения',
  approved: 'Принята',
  rejected: 'Отклонена',
}

function when(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function personName(person) {
  const name = String(person.name || person.firstName || '').trim()
  if (name) return name
  if (person.username) return `@${person.username}`
  return `ID ${person.userId}`
}

function matchQuery(hay, query) {
  if (!query) return true
  return String(hay || '').toLowerCase().includes(query)
}

export default function GroupAdminsDesk({ onOpenUser = null }) {
  const [segment, setSegment] = useState('roster')
  const [groups, setGroups] = useState([])
  const [apps, setApps] = useState([])
  const [drops, setDrops] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [keyOnce, setKeyOnce] = useState('')
  const [query, setQuery] = useState('')
  const [busyKey, setBusyKey] = useState('')
  const [rejectId, setRejectId] = useState(null)
  const [rejectNote, setRejectNote] = useState('')
  const [seatItem, setSeatItem] = useState(null)
  const [appointUserId, setAppointUserId] = useState('')
  const [appointChatId, setAppointChatId] = useState('')
  const [appointPositionId, setAppointPositionId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [board, appData, dropData] = await Promise.all([
        fetchRightsBoard(),
        fetchGroupApplications(),
        fetchAdminDrops(),
      ])
      setGroups(Array.isArray(board?.groups) ? board.groups : [])
      setApps(Array.isArray(appData?.items) ? appData.items : [])
      setDrops(Array.isArray(dropData?.items) ? dropData.items : [])
    } catch (err) {
      setError(err?.message || 'Не удалось открыть администраторов групп')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const q = query.trim().toLowerCase()

  const roster = useMemo(() => {
    return groups
      .map((group) => {
        const seats = (group.seats || []).filter((seat) => {
          if (seat.paused || seat.kind === 'spamblock') return true
          const blob = [
            personName(seat),
            seat.username,
            seat.userId,
            seat.position,
            group.title,
          ].join(' ')
          return matchQuery(blob, q)
        })
        if (q && seats.length === 0 && !matchQuery(group.title, q)) return null
        return { ...group, seats }
      })
      .filter(Boolean)
  }, [groups, q])

  const pendingApps = useMemo(
    () => apps.filter((item) => (item.status || 'pending') === 'pending').length,
    [apps],
  )
  const pendingDrops = useMemo(
    () => drops.filter((item) => item.status === 'pending').length,
    [drops],
  )
  const seatTotal = useMemo(
    () => groups.reduce((sum, group) => sum + ((group.seats || []).length), 0),
    [groups],
  )

  const seatChoices = useMemo(() => adminSeatChoices(groups), [groups])
  const appointPosts = useMemo(() => {
    const chatId = Number(appointChatId)
    const group = seatChoices.find((item) => Number(item.chatId) === chatId)
    return group?.posts || []
  }, [seatChoices, appointChatId])

  const dismiss = async (chatId, userId) => {
    const key = `d:${chatId}:${userId}`
    if (busyKey) return
    setBusyKey(key)
    setError('')
    setNotice('')
    try {
      await dismissGroupAdmin({ chat_id: chatId, user_id: userId })
      setNotice('Должность снята')
      await load()
    } catch (err) {
      setError(err?.message || 'Снять не удалось')
    } finally {
      setBusyKey('')
    }
  }

  const approveApp = async (item, positionId = null) => {
    setBusyKey(`a:${item.id}`)
    setError('')
    setNotice('')
    setKeyOnce('')
    try {
      const data = await decideGroupApplication({
        application_id: item.id,
        approve: true,
        note: '',
        ...(positionId ? { position_id: positionId } : {}),
      })
      setSeatItem(null)
      setApps((list) => list.filter((row) => row.id !== item.id))
      setKeyOnce(data?.entryKey || '')
      const placed = data?.position && data?.group ? ` Должность: «${data.position}» в «${data.group}».` : ''
      setNotice(data?.entryKey
        ? `Заявка одобрена.${placed} Ключ показан ниже — передайте, если сообщение в бота не дошло.`
        : `Заявка одобрена.${placed}`)
      await load()
    } catch (err) {
      setError(err?.message || 'Одобрить не удалось')
    } finally {
      setBusyKey('')
    }
  }

  const rejectApp = async (item) => {
    const reason = rejectNote.trim()
    if (reason.length < 2) {
      setError('Отказ сохраняется только с причиной')
      return
    }
    setBusyKey(`a:${item.id}`)
    setError('')
    setNotice('')
    try {
      await decideGroupApplication({
        application_id: item.id,
        approve: false,
        note: reason,
      })
      setRejectId(null)
      setRejectNote('')
      setNotice('Заявка отклонена')
      await load()
    } catch (err) {
      setError(err?.message || 'Отказ не сохранился')
    } finally {
      setBusyKey('')
    }
  }

  const decideDrop = async (item, approve) => {
    if (busyKey) return
    setBusyKey(`drop:${item.id}`)
    setError('')
    setNotice('')
    try {
      const data = await decideAdminDrop(item.id, approve)
      setNotice(data?.toast || (approve ? 'Админка снята' : 'Заявка отклонена'))
      await load()
    } catch (err) {
      setError(err?.message || 'Решение не сохранилось')
    } finally {
      setBusyKey('')
    }
  }

  const submitAppoint = async (event) => {
    event.preventDefault()
    const userId = Number(String(appointUserId).trim())
    const chatId = Number(appointChatId)
    const positionId = Number(appointPositionId)
    if (!Number.isSafeInteger(userId) || userId < 1) {
      setError('Укажите корректный ID пользователя')
      return
    }
    if (!Number.isSafeInteger(chatId) || !Number.isSafeInteger(positionId) || positionId < 1) {
      setError('Выберите группу и должность')
      return
    }
    setBusyKey('appoint')
    setError('')
    setNotice('')
    try {
      await appointGroupAdmin({
        chat_id: chatId,
        user_id: userId,
        position_id: positionId,
      })
      setNotice('Человек назначен на должность')
      setAppointUserId('')
      setAppointPositionId(null)
      await load()
      setSegment('roster')
    } catch (err) {
      setError(err?.message || 'Назначить не удалось')
    } finally {
      setBusyKey('')
    }
  }

  const filteredApps = useMemo(() => {
    if (!q) return apps
    return apps.filter((item) => {
      const person = applicationPerson(item)
      return matchQuery([person.title, person.username, item.userId, item.group, item.position].join(' '), q)
    })
  }, [apps, q])

  const filteredDrops = useMemo(() => {
    if (!q) return drops
    return drops.filter((item) => matchQuery(
      [item.name, item.username, item.userId, item.group, item.actorName].join(' '),
      q,
    ))
  }, [drops, q])

  return (
    <div className="gad">
      <header className="gad-hero">
        <h3>Администраторы групп</h3>
        <p>
          Список админов официальных групп, заявки на вступление и снятие, самостоятельное назначение.
          Названия и права должностей меняет только создатель проекта.
        </p>
        <p className="gad-note">
          {seatTotal} мест · {pendingApps} заявок · {pendingDrops} снятий
        </p>
      </header>

      <nav className="gad-segments" aria-label="Разделы администраторов групп">
        {SEGMENTS.map((item) => {
          const count = item.id === 'roster' ? seatTotal
            : item.id === 'apps' ? pendingApps
              : item.id === 'drops' ? pendingDrops
                : null
          return (
            <button
              key={item.id}
              type="button"
              className={`gad-seg${segment === item.id ? ' is-on' : ''}`}
              aria-current={segment === item.id ? 'page' : undefined}
              onClick={() => setSegment(item.id)}
            >
              {item.label}
              {count != null && <span className="gad-seg-count">{count}</span>}
            </button>
          )
        })}
      </nav>

      <div className="gad-toolbar">
        {segment !== 'appoint' && (
          <input
            className="gad-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по имени, группе, должности, ID"
            aria-label="Поиск"
          />
        )}
        <button type="button" className="gad-btn" onClick={load} disabled={loading}>
          {loading ? 'Обновляем…' : 'Обновить'}
        </button>
      </div>

      {error && <p className="gad-error" role="alert">{error}</p>}
      {notice && <p className="gad-status" role="status">{notice}</p>}
      {keyOnce && (
        <p className="gad-status" data-copyable="1">
          Личный ключ, один показ: <code>{keyOnce}</code>
        </p>
      )}

      {segment === 'roster' && (
        <div className="gad-panel" key="roster">
          {loading && groups.length === 0 && <p className="gad-empty">Собираем список…</p>}
          {!loading && roster.length === 0 && <p className="gad-empty">Администраторов групп пока нет</p>}
          <div className="gad-groups">
            {roster.map((group) => (
              <article key={group.chatId} className="gad-group">
                <div className="gad-group-head">
                  <strong>{group.title || group.chatId}</strong>
                  <span>{(group.seats || []).length} чел.</span>
                </div>
                {(group.seats || []).length === 0 ? (
                  <p className="gad-meta">Пока никого на должностях</p>
                ) : (
                  <ul className="gad-people">
                    {(group.seats || []).map((seat) => {
                      const key = `d:${group.chatId}:${seat.userId}`
                      const paused = Boolean(seat.paused)
                      return (
                        <li key={`${group.chatId}-${seat.userId}`} className="gad-person">
                          <div className="gad-person-main">
                            <strong>{personName(seat)}</strong>
                            <span>
                              {seat.username ? `@${seat.username} · ` : ''}
                              {seat.position || 'должность'}
                              {seat.rank != null ? ` · ранг ${seat.rank}` : ''}
                              {paused ? ' · на паузе' : ''}
                            </span>
                          </div>
                          <div className="gad-person-actions">
                            {onOpenUser && (
                              <button type="button" className="gad-btn" onClick={() => onOpenUser(seat.userId)}>
                                Игрок
                              </button>
                            )}
                            {!paused && Number(seat.rank) < 5 && (
                              <button
                                type="button"
                                className="gad-btn gad-btn-danger"
                                disabled={busyKey === key}
                                onClick={() => dismiss(group.chatId, seat.userId)}
                              >
                                {busyKey === key ? '…' : 'Снять'}
                              </button>
                            )}
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {segment === 'apps' && (
        <div className="gad-panel" key="apps">
          {loading && apps.length === 0 && <p className="gad-empty">Загрузка заявок…</p>}
          {!loading && filteredApps.length === 0 && <p className="gad-empty">Заявок в админы нет</p>}
          <ul className="gad-list">
            {filteredApps.map((item) => {
              const person = applicationPerson(item)
              const pending = (item.status || 'pending') === 'pending'
              return (
                <li key={item.id} className="gad-card">
                  <div className="gad-card-head">
                    <strong>{person.title}</strong>
                    <span className="gad-meta">{item.group}</span>
                  </div>
                  <p className="gad-meta">
                    {person.username ? <><CopyableUsername value={person.username} />{' · '}</> : null}
                    {item.position} · ранг {item.rank} · {APP_STATUS[item.status] || item.status}
                    {item.at ? ` · ${when(item.at)}` : ''}
                  </p>
                  {item.alreadySeated && pending && (
                    <p className="gad-meta">Уже на должности — заявка нужна для ключа.</p>
                  )}
                  {(item.advice || []).map((advice) => (
                    <p className="gad-meta" key={`${item.id}-${advice.actorId}`}>
                      Рекомендация от {advice.name} — {advice.verdict === 'fit' ? 'Подходит' : 'Не подходит'}
                      {advice.note ? `. ${advice.note}` : ''}
                    </p>
                  ))}
                  <p className="gad-meta"><CopyableId value={item.userId} label="id игрока" /></p>
                  {item.body && <p className="gad-body">{item.body}</p>}
                  <div className="gad-actions">
                    {onOpenUser && (
                      <button type="button" className="gad-btn" onClick={() => onOpenUser(item.userId)}>
                        Игрок
                      </button>
                    )}
                    {pending && (
                      <>
                        <button
                          type="button"
                          className="gad-btn gad-btn-primary"
                          disabled={busyKey === `a:${item.id}`}
                          onClick={() => approveApp(item)}
                        >
                          Одобрить
                        </button>
                        <button
                          type="button"
                          className="gad-btn"
                          disabled={busyKey === `a:${item.id}`}
                          onClick={() => { setSeatItem(item); setError('') }}
                        >
                          Другая должность
                        </button>
                        <button
                          type="button"
                          className="gad-btn gad-btn-danger"
                          disabled={busyKey === `a:${item.id}`}
                          onClick={() => { setRejectId(item.id); setRejectNote(''); setError('') }}
                        >
                          Отказать
                        </button>
                      </>
                    )}
                  </div>
                  {rejectId === item.id && pending && (
                    <form
                      className="gad-reject"
                      onSubmit={(event) => { event.preventDefault(); rejectApp(item) }}
                    >
                      <label>
                        Причина отказа
                        <textarea
                          value={rejectNote}
                          onChange={(event) => setRejectNote(event.target.value)}
                          rows={3}
                        />
                      </label>
                      <button
                        type="submit"
                        className="gad-btn gad-btn-danger"
                        disabled={busyKey === `a:${item.id}` || rejectNote.trim().length < 2}
                      >
                        Сохранить отказ
                      </button>
                    </form>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {segment === 'drops' && (
        <div className="gad-panel" key="drops">
          {loading && drops.length === 0 && <p className="gad-empty">Собираем заявки на снятие…</p>}
          {!loading && filteredDrops.length === 0 && <p className="gad-empty">Заявок на снятие нет</p>}
          <ul className="gad-list">
            {filteredDrops.map((item) => {
              const waiting = item.status === 'pending'
              return (
                <li key={item.id} className="gad-card">
                  <div className="gad-card-head">
                    <strong>
                      {item.name}
                      {item.username ? ` · @${item.username}` : ''}
                    </strong>
                    <span className="gad-meta">{DROP_STATUS[item.status] || item.status}</span>
                  </div>
                  <p className="gad-meta">
                    {item.group} · просит {item.actorName}
                    {item.at ? ` · ${when(item.at)}` : ''}
                    {' · '}
                    id {item.userId}
                  </p>
                  {waiting && (
                    <div className="gad-actions">
                      <button
                        type="button"
                        className="gad-btn gad-btn-primary"
                        disabled={busyKey === `drop:${item.id}`}
                        onClick={() => decideDrop(item, true)}
                      >
                        Принять снятие
                      </button>
                      <button
                        type="button"
                        className="gad-btn"
                        disabled={busyKey === `drop:${item.id}`}
                        onClick={() => decideDrop(item, false)}
                      >
                        Отклонить
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {segment === 'appoint' && (
        <form className="gad-form" key="appoint" onSubmit={submitAppoint}>
          <p className="gad-meta">
            Назначьте человека на существующую должность. Создать или переименовать должность здесь нельзя.
          </p>
          <label>
            ID пользователя
            <input
              value={appointUserId}
              onChange={(event) => setAppointUserId(event.target.value.replace(/[^\d]/g, '').slice(0, 15))}
              inputMode="numeric"
              placeholder="Например 123456789"
              required
            />
          </label>
          <label>
            Группа
            <select
              value={appointChatId}
              onChange={(event) => {
                setAppointChatId(event.target.value)
                setAppointPositionId(null)
              }}
              required
            >
              <option value="">Выберите группу</option>
              {seatChoices.map((group) => (
                <option key={group.chatId} value={String(group.chatId)}>
                  {group.title}
                </option>
              ))}
            </select>
          </label>
          {appointChatId && (
            <div>
              <p className="gad-meta">Должность</p>
              {appointPosts.length === 0 ? (
                <p className="gad-meta">В этой группе нет доступных должностей администратора.</p>
              ) : (
                <div className="gad-posts">
                  {appointPosts.map((post) => (
                    <button
                      key={post.id}
                      type="button"
                      className={`gad-post${Number(appointPositionId) === Number(post.id) ? ' is-on' : ''}`}
                      aria-pressed={Number(appointPositionId) === Number(post.id)}
                      onClick={() => setAppointPositionId(post.id)}
                    >
                      <strong>{post.title}</strong>
                      <span>ранг {post.rank}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <button
            type="submit"
            className="gad-btn gad-btn-primary"
            disabled={busyKey === 'appoint' || !appointPositionId}
          >
            {busyKey === 'appoint' ? 'Назначаем…' : 'Назначить'}
          </button>
        </form>
      )}

      {seatItem && (
        <ApproveSeat
          item={seatItem}
          busy={busyKey === `a:${seatItem.id}`}
          error={error}
          onClose={() => { if (busyKey !== `a:${seatItem.id}`) setSeatItem(null) }}
          onApprove={(positionId) => approveApp(seatItem, positionId)}
        />
      )}
    </div>
  )
}
