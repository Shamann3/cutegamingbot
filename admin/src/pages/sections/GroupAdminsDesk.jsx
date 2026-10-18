import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  searchAdminUsers,
} from '../../lib/adminClient'
import { applicationPerson } from '../../lib/applicationPerson'
import { adminSeatChoices, positionKindLabel } from '../../lib/seatChoice'
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

function typedUserId(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (!digits) return null
  const id = Number(digits)
  return Number.isSafeInteger(id) && id > 0 ? id : null
}

function personBits(item) {
  if (!item) return null
  const id = Number(item.userId ?? item.user_id ?? item.id)
  if (!Number.isSafeInteger(id) || id < 1) return null
  const username = String(item.username || '').replace(/^@/, '')
  const name = String(item.displayName || item.display_name || item.firstName || item.first_name || item.name || '').trim()
  return { id, username, name }
}

function AppointPersonField({ text, onText, userId, onUserId }) {
  const [hits, setHits] = useState([])
  const [phase, setPhase] = useState('idle')
  const [picked, setPicked] = useState(null)
  const onUserIdRef = useRef(onUserId)
  onUserIdRef.current = onUserId
  const inputRef = useRef(null)

  useEffect(() => {
    const query = String(text || '').trim()
    const bare = query.replace(/^@/, '')
    if (bare.length < 2) {
      setHits([])
      setPicked(null)
      setPhase('idle')
      return undefined
    }
    let cancelled = false
    const timer = window.setTimeout(async () => {
      setPhase('loading')
      try {
        const data = await searchAdminUsers(query)
        if (cancelled) return
        const items = (Array.isArray(data?.results) ? data.results : Array.isArray(data?.items) ? data.items : []).slice(0, 6)
        setHits(items)
        const exact = items
          .map((item) => ({ item, bits: personBits(item) }))
          .find(({ bits }) => bits && (
            String(bits.id) === bare
            || bits.username.toLowerCase() === bare.toLowerCase()
          ))
        if (exact?.bits) {
          setPicked(exact.item)
          onUserIdRef.current(exact.bits.id)
          setPhase('ready')
        } else {
          setPicked(null)
          setPhase(items.length ? 'ready' : 'empty')
        }
      } catch {
        if (cancelled) return
        setHits([])
        setPicked(null)
        setPhase('error')
      }
    }, 180)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [text])

  const type = (value) => {
    onText(value)
    onUserId(typedUserId(value))
    setPicked(null)
  }

  const choose = (person) => {
    const bits = personBits(person)
    if (!bits) return
    setPicked(person)
    onUserId(bits.id)
    onText(bits.username ? `@${bits.username}` : bits.name || String(bits.id))
    inputRef.current?.focus()
  }

  const chosen = personBits(picked)
  const shownId = chosen?.id || userId

  return (
    <div className="gad-person-field">
      <label htmlFor="gad-person-input">Кому</label>
      <div className="gad-person-box">
        <input
          id="gad-person-input"
          ref={inputRef}
          type="text"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="@username, имя или id"
          value={text}
          onChange={(event) => type(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            if (hits.length === 1) choose(hits[0])
          }}
        />
        {text ? (
          <button type="button" className="gad-person-clear" onClick={() => type('')}>
            Стереть
          </button>
        ) : null}
      </div>
      {phase === 'loading' && <p className="gad-hint">Ищем…</p>}
      {phase === 'empty' && !typedUserId(text) && (
        <p className="gad-hint">Такого человека нет. Проверьте @username или впишите id.</p>
      )}
      {phase === 'error' && (
        <p className="gad-hint">Поиск не ответил. Id можно вписать цифрами.</p>
      )}
      {chosen && (
        <p className="gad-picked" role="status">
          Выбран: <strong>{chosen.name || chosen.username || chosen.id}</strong>
          {chosen.username ? ` · @${chosen.username}` : ''}
          {' · '}
          id {chosen.id}
        </p>
      )}
      {!chosen && shownId && (
        <p className="gad-picked" role="status">Будет назначен id {shownId}</p>
      )}
      {hits.length > 0 && !chosen && (
        <ul className="gad-hits">
          {hits.map((item) => {
            const bits = personBits(item)
            if (!bits) return null
            return (
              <li key={bits.id}>
                <button type="button" onClick={() => choose(item)}>
                  <strong>{bits.name || bits.username || bits.id}</strong>
                  <span>
                    {bits.username ? `@${bits.username} · ` : ''}
                    id {bits.id}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
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
  const [dismissAsk, setDismissAsk] = useState(null)

  const [personText, setPersonText] = useState('')
  const [appointUserId, setAppointUserId] = useState(null)
  const [appointChatId, setAppointChatId] = useState('')
  const [appointPositionId, setAppointPositionId] = useState(null)
  const [appointReason, setAppointReason] = useState('')
  const [termStart, setTermStart] = useState('')
  const [termEnd, setTermEnd] = useState('')
  const [everywhere, setEverywhere] = useState(false)
  const [groupFilter, setGroupFilter] = useState('')

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
          if (!q) return true
          if (seat.paused || seat.kind === 'spamblock') {
            const blob = [
              personName(seat),
              seat.username,
              seat.userId,
              seat.position,
              group.title,
              seat.kind,
            ].join(' ')
            return matchQuery(blob, q)
          }
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

  const seatChoices = useMemo(
    () => adminSeatChoices(groups, { includeSpamblock: true }),
    [groups],
  )

  const filteredGroups = useMemo(() => {
    const needle = groupFilter.trim().toLowerCase()
    if (!needle) return seatChoices
    return seatChoices.filter((group) => matchQuery(`${group.title} ${group.chatId}`, needle))
  }, [seatChoices, groupFilter])

  const appointPosts = useMemo(() => {
    if (everywhere) {
      // Для «во все группы» берём должности из выбранной группы-шаблона.
      const chatId = Number(appointChatId)
      const group = seatChoices.find((item) => Number(item.chatId) === chatId)
      return group?.posts || []
    }
    const chatId = Number(appointChatId)
    const group = seatChoices.find((item) => Number(item.chatId) === chatId)
    return group?.posts || []
  }, [seatChoices, appointChatId, everywhere])

  const selectedPost = useMemo(
    () => appointPosts.find((post) => Number(post.id) === Number(appointPositionId)) || null,
    [appointPosts, appointPositionId],
  )
  const spamPick = selectedPost?.kind === 'spamblock'
  const selectedGroup = useMemo(
    () => seatChoices.find((item) => Number(item.chatId) === Number(appointChatId)) || null,
    [seatChoices, appointChatId],
  )

  const resetAppoint = () => {
    setPersonText('')
    setAppointUserId(null)
    setAppointChatId('')
    setAppointPositionId(null)
    setAppointReason('')
    setTermStart('')
    setTermEnd('')
    setEverywhere(false)
    setGroupFilter('')
  }

  const dismiss = async (chatId, userId) => {
    const key = `d:${chatId}:${userId}`
    if (busyKey) return
    setBusyKey(key)
    setError('')
    setNotice('')
    try {
      await dismissGroupAdmin({ chat_id: chatId, user_id: userId })
      setNotice('Должность снята')
      setDismissAsk(null)
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
    const userId = Number(appointUserId || typedUserId(personText))
    const chatId = Number(appointChatId)
    const positionId = Number(appointPositionId)
    if (!Number.isSafeInteger(userId) || userId < 1) {
      setError('Выберите человека или укажите корректный ID')
      return
    }
    if (!Number.isSafeInteger(chatId) || !Number.isSafeInteger(positionId) || positionId < 1) {
      setError('Выберите группу и должность')
      return
    }
    if (spamPick && !termEnd) {
      setError('Для спам-блока укажите, по какое число держать должность')
      return
    }
    setBusyKey('appoint')
    setError('')
    setNotice('')
    setKeyOnce('')
    try {
      const data = await appointGroupAdmin({
        chat_id: chatId,
        user_id: userId,
        position_id: positionId,
        reason: appointReason.trim() || 'Назначение из администраторов групп',
        term_start: spamPick ? termStart : '',
        term_end: spamPick ? termEnd : '',
        everywhere,
      })
      setKeyOnce(data?.entryKey || '')
      setNotice(
        everywhere
          ? `Должность выдана в ${data?.placed || 'нескольких'} официальных группах.`
          : (data?.telegram || 'Человек назначен на должность'),
      )
      resetAppoint()
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

  const appointReady = Boolean(
    (appointUserId || typedUserId(personText))
    && appointChatId
    && appointPositionId
    && (!spamPick || termEnd),
  )

  return (
    <div className="gad">
      <header className="gad-hero">
        <h3>Администраторы групп</h3>
        <p>
          Список, заявки, снятие и назначение — включая спам-блок.
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
                      const spam = seat.kind === 'spamblock'
                      const asking = dismissAsk
                        && Number(dismissAsk.chatId) === Number(group.chatId)
                        && Number(dismissAsk.userId) === Number(seat.userId)
                      return (
                        <li
                          key={`${group.chatId}-${seat.userId}`}
                          className={`gad-person${spam ? ' is-spam' : ''}${paused ? ' is-paused' : ''}`}
                        >
                          <div className="gad-person-main">
                            <strong>{personName(seat)}</strong>
                            <span>
                              {seat.username ? `@${seat.username} · ` : ''}
                              {seat.position || 'должность'}
                              {seat.rank != null ? ` · ранг ${seat.rank}` : ''}
                              {paused ? ' · на паузе' : ''}
                              {spam && seat.termEnd ? ` · до ${seat.termEnd}` : ''}
                            </span>
                            <span className="gad-chips">
                              {spam && <span className="gad-chip gad-chip-spam">Спам-блок</span>}
                              {paused && <span className="gad-chip">Пауза</span>}
                            </span>
                          </div>
                          <div className="gad-person-actions">
                            {onOpenUser && (
                              <button type="button" className="gad-btn" onClick={() => onOpenUser(seat.userId)}>
                                Игрок
                              </button>
                            )}
                            {!paused && Number(seat.rank) < 5 && !asking && (
                              <button
                                type="button"
                                className="gad-btn gad-btn-danger"
                                disabled={Boolean(busyKey)}
                                onClick={() => setDismissAsk({
                                  chatId: group.chatId,
                                  userId: seat.userId,
                                  name: personName(seat),
                                  position: seat.position,
                                  group: group.title,
                                })}
                              >
                                Снять
                              </button>
                            )}
                          </div>
                          {asking && (
                            <div className="gad-confirm" role="alertdialog" aria-label="Подтверждение снятия">
                              <p>
                                Снять «{dismissAsk.position || 'должность'}» у {dismissAsk.name}
                                {dismissAsk.group ? ` в «${dismissAsk.group}»` : ''}?
                                Человек останется в группе без префикса.
                              </p>
                              <div className="gad-actions">
                                <button
                                  type="button"
                                  className="gad-btn gad-btn-danger"
                                  disabled={busyKey === key}
                                  onClick={() => dismiss(group.chatId, seat.userId)}
                                >
                                  {busyKey === key ? 'Снимаем…' : 'Да, снять'}
                                </button>
                                <button
                                  type="button"
                                  className="gad-btn"
                                  disabled={busyKey === key}
                                  onClick={() => setDismissAsk(null)}
                                >
                                  Отмена
                                </button>
                              </div>
                            </div>
                          )}
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
        <form className="gad-form gad-form-wide" key="appoint" onSubmit={submitAppoint}>
          <div className="gad-step">
            <span className="gad-step-num">1</span>
            <div>
              <h4>Человек</h4>
              <p className="gad-meta">Найдите по @username, имени или id — как в карточке должности.</p>
            </div>
          </div>
          <AppointPersonField
            text={personText}
            onText={setPersonText}
            userId={appointUserId}
            onUserId={setAppointUserId}
          />

          <div className="gad-step">
            <span className="gad-step-num">2</span>
            <div>
              <h4>Группа</h4>
              <p className="gad-meta">
                {everywhere
                  ? 'Должность встанет во все официальные группы. Ниже выберите группу-образец с нужной должностью.'
                  : 'Выберите одну официальную группу — должность встанет только туда.'}
              </p>
            </div>
          </div>

          <label className="gad-switch">
            <input
              type="checkbox"
              checked={everywhere}
              onChange={(event) => {
                setEverywhere(event.target.checked)
                setAppointPositionId(null)
              }}
            />
            <span>Во все официальные группы</span>
          </label>

          <input
            className="gad-search"
            type="search"
            value={groupFilter}
            onChange={(event) => setGroupFilter(event.target.value)}
            placeholder="Найти группу по названию"
            aria-label="Фильтр групп"
          />

          {filteredGroups.length === 0 ? (
            <p className="gad-empty">Официальных групп по запросу нет</p>
          ) : (
            <div className="gad-pick-grid" role="listbox" aria-label="Официальные группы">
              {filteredGroups.map((group) => {
                const on = Number(appointChatId) === Number(group.chatId)
                const postCount = (group.posts || []).length
                return (
                  <button
                    key={group.chatId}
                    type="button"
                    role="option"
                    aria-selected={on}
                    className={`gad-pick${on ? ' is-on' : ''}`}
                    onClick={() => {
                      setAppointChatId(String(group.chatId))
                      setAppointPositionId(null)
                    }}
                  >
                    <strong>{group.title}</strong>
                    <span>
                      {postCount
                        ? `${postCount} ${postCount === 1 ? 'должность' : 'должностей'}`
                        : 'нет должностей'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {appointChatId && (
            <>
              <div className="gad-step">
                <span className="gad-step-num">3</span>
                <div>
                  <h4>Должность</h4>
                  <p className="gad-meta">
                    {selectedGroup
                      ? `В «${selectedGroup.title}»${everywhere ? ' — образец для всех групп' : ''}.`
                      : 'Выберите должность администратора или спам-блок.'}
                  </p>
                </div>
              </div>
              {appointPosts.length === 0 ? (
                <p className="gad-meta">В этой группе нет доступных должностей. Их добавляет создатель во вкладке «Должности».</p>
              ) : (
                <div className="gad-posts" role="listbox" aria-label="Должности">
                  {appointPosts.map((post) => {
                    const on = Number(appointPositionId) === Number(post.id)
                    const spam = post.kind === 'spamblock'
                    return (
                      <button
                        key={post.id}
                        type="button"
                        role="option"
                        aria-selected={on}
                        className={`gad-post${on ? ' is-on' : ''}${spam ? ' is-spam' : ''}`}
                        onClick={() => {
                          setAppointPositionId(post.id)
                          if (post.kind !== 'spamblock') {
                            setTermStart('')
                            setTermEnd('')
                          }
                        }}
                      >
                        <strong>{post.title}</strong>
                        <span>
                          {positionKindLabel(post.kind)}
                          {post.kind !== 'spamblock' ? ` · ранг ${post.rank}` : ' · нужен срок'}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </>
          )}

          {spamPick && (
            <div className="gad-dates">
              <div className="gad-step">
                <span className="gad-step-num">4</span>
                <div>
                  <h4>Срок спам-блока</h4>
                  <p className="gad-meta">Конец обязателен. После даты должность снимется сама.</p>
                </div>
              </div>
              <div className="gad-date-row">
                <label>
                  С какого числа
                  <input
                    type="date"
                    value={termStart}
                    onChange={(event) => setTermStart(event.target.value)}
                  />
                </label>
                <label>
                  По какое число
                  <input
                    type="date"
                    value={termEnd}
                    onChange={(event) => setTermEnd(event.target.value)}
                    required
                  />
                </label>
              </div>
            </div>
          )}

          {appointPositionId && (
            <label>
              Для чего
              <input
                value={appointReason}
                onChange={(event) => setAppointReason(event.target.value)}
                placeholder="Можно оставить пустым"
                maxLength={200}
              />
            </label>
          )}

          {appointReady && (
            <div className="gad-summary" role="status">
              <strong>Готово к назначению</strong>
              <span>
                {personText || `id ${appointUserId}`}
                {' → '}
                {selectedPost?.title || 'должность'}
                {everywhere ? ' · все официальные группы' : selectedGroup ? ` · «${selectedGroup.title}»` : ''}
                {spamPick && termEnd ? ` · до ${termEnd}` : ''}
              </span>
            </div>
          )}

          <div className="gad-form-actions">
            <button
              type="submit"
              className="gad-btn gad-btn-primary"
              disabled={busyKey === 'appoint' || !appointReady}
            >
              {busyKey === 'appoint' ? 'Назначаем…' : spamPick ? 'Выдать спам-блок' : 'Назначить'}
            </button>
            <button
              type="button"
              className="gad-btn"
              disabled={busyKey === 'appoint'}
              onClick={resetAppoint}
            >
              Очистить
            </button>
          </div>
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
