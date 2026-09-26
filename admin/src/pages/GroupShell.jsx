import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  appointGroupAdmin,
  decideGroupApplication,
  fetchGroupApplications,
  fetchGroupPositions,
  fetchGroupSummary,
  groupRealmAct,
  markGroupOfficial,
  searchGroupsStudio,
} from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { punishmentHours } from '../lib/gateRecovery'
import FirstRun, { GROUP_STEPS, firstRunSeen } from '../components/FirstRun'

const ACTIONS = [
  { id: 'mute', label: 'Мут', right: 'punish_mute', needsUntil: true },
  { id: 'unmute', label: 'Размут', right: 'punish_mute', needsUntil: false },
  { id: 'kick', label: 'Кик', right: 'punish_kick', needsUntil: false },
  { id: 'warn', label: 'Варн', right: 'punish_warn', needsUntil: true },
  { id: 'ban', label: 'Бан', right: 'punish_ban', needsUntil: true },
  { id: 'unban', label: 'Разбан', right: 'punish_ban', needsUntil: false },
]

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function when(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function tabsFor(rights, isCreator) {
  const has = (key) => isCreator || rights.has(key)
  const items = [{ id: 'overview', label: 'Обзор' }]
  if (has('view_members') || [...rights].some((r) => r.startsWith('punish_'))) items.push({ id: 'people', label: 'Люди' })
  if (has('view_archive')) items.push({ id: 'archive', label: 'Архив' })
  if (has('view_analytics')) items.push({ id: 'analytics', label: 'Аналитика' })
  items.push({ id: 'more', label: 'Ещё' })
  return items
}

export default function GroupShell({ portrait, onLeave, onStaffApply }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const isCreator = Boolean(portrait?.isOwner)
  const groups = portrait?.groups || []
  const [chatId, setChatId] = useState(groups[0]?.chatId ?? null)
  const current = groups.find((g) => g.chatId === chatId) || null
  const rights = useMemo(() => new Set(current?.rights || []), [current])
  const tabs = useMemo(() => tabsFor(rights, isCreator), [rights, isCreator])
  const [tab, setTab] = useState('overview')
  const [chapter, setChapter] = useState(false)
  const [lockOpen, setLockOpen] = useState(false)
  const [coach, setCoach] = useState(() => !firstRunSeen('epsilon.onboard.group.v1'))
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [entryKey, setEntryKey] = useState('')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('mute')
  const [hours, setHours] = useState('1')
  const [reason, setReason] = useState('')
  const [acting, setActing] = useState(false)
  const [positions, setPositions] = useState([])
  const [apps, setApps] = useState([])
  const [appointUser, setAppointUser] = useState('')
  const [appointPos, setAppointPos] = useState('')
  const [appointReason, setAppointReason] = useState('')

  const activeTab = tabs.some((item) => item.id === tab) ? tab : 'overview'
  const allowedActions = ACTIONS.filter((item) => isCreator || rights.has(item.right))
  const selectedAction = allowedActions.find((item) => item.id === action) || allowedActions[0]

  const loadSummary = useCallback(async (id) => {
    if (!id) {
      setSummary(null)
      return
    }
    setLoading(true)
    setError('')
    try {
      setSummary(await fetchGroupSummary(id))
    } catch (err) {
      setSummary(null)
      setError(err.message || 'Карточка группы не открылась')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadSummary(chatId) }, [chatId, loadSummary])

  const openCreator = async () => {
    setChapter(true)
    setError('')
    try {
      if (chatId) {
        const data = await fetchGroupPositions(chatId)
        setPositions(data.positions || [])
      }
      const queue = await fetchGroupApplications()
      setApps(queue.items || [])
    } catch (err) {
      setError(err.message || 'Должности не открылись')
    }
  }

  const onSearch = async (event) => {
    event.preventDefault()
    if (!query.trim()) {
      setError('Введите название, @username или id')
      return
    }
    setError('')
    try {
      const data = await searchGroupsStudio(query.trim())
      const items = Array.isArray(data?.items) ? data.items : []
      setHits(items)
      if (!items.length) setError('Такой группы в базе нет')
    } catch (err) {
      setError(err.message || 'Поиск не выполнился')
    }
  }

  const makeOfficial = async (row) => {
    setError('')
    try {
      await markGroupOfficial({
        chat_id: row.chat_id,
        title: row.name || '',
        username: row.username || '',
        official: true,
      })
      setNotice('Группа официальная. Вернитесь к дверям, чтобы увидеть её в списке.')
      setChatId(row.chat_id)
    } catch (err) {
      setError(err.message || 'Не удалось отметить группу')
    }
  }

  const punish = async (event) => {
    event.preventDefault()
    if (!chatId || !selectedAction) return
    const uid = Number(String(userId).replace(/\D/g, ''))
    if (!uid) {
      setError('Нужен id человека')
      return
    }
    const untilSec = selectedAction.needsUntil ? punishmentHours(hours) : null
    if (selectedAction.needsUntil && untilSec == null) {
      setError('Срок укажите в часах: от доли часа до года')
      return
    }
    setActing(true)
    setError('')
    setNotice('')
    try {
      await groupRealmAct({
        chat_id: chatId,
        user_id: uid,
        action: selectedAction.id,
        until_sec: untilSec,
        reason: reason.trim(),
      })
      setNotice('Действие записано в этот чат')
      await loadSummary(chatId)
    } catch (err) {
      setError(err.message || 'Действие не прошло')
    } finally {
      setActing(false)
    }
  }

  const appoint = async (event) => {
    event.preventDefault()
    const uid = Number(String(appointUser).replace(/\D/g, ''))
    if (!chatId || !uid || !appointPos) {
      setError('Нужны группа, id человека и должность')
      return
    }
    setError('')
    try {
      const data = await appointGroupAdmin({
        chat_id: chatId,
        user_id: uid,
        position_id: Number(appointPos),
        reason: appointReason.trim(),
      })
      setEntryKey(data.entryKey || '')
      setNotice('Человек назначен. Ключ показан один раз.')
    } catch (err) {
      setError(err.message || 'Назначить не удалось')
    }
  }

  const decide = async (item, approve) => {
    const note = approve ? '' : window.prompt('Причина отказа')
    if (!approve && !note) return
    setError('')
    try {
      const data = await decideGroupApplication({
        application_id: item.id,
        approve,
        note: note || '',
      })
      if (data.entryKey) setEntryKey(data.entryKey)
      setApps((list) => list.filter((row) => row.id !== item.id))
      setNotice(approve ? 'Заявка одобрена. Ключ показан один раз.' : 'Заявка отклонена')
    } catch (err) {
      setError(err.message || 'Решение не сохранилось')
    }
  }

  const mods = summary?.moderation

  return (
    <div className={`realm-root${personal ? ' is-personal' : ''}`}>
      {coach && (
        <FirstRun storageKey="epsilon.onboard.group.v1" steps={GROUP_STEPS} onDone={() => setCoach(false)} />
      )}
      <header className="realm-top">
        <button type="button" className="realm-back" onClick={onLeave}>Двери</button>
        <div>
          <h1>{summary?.chat?.title || current?.title || 'Группы'}</h1>
          <p className="realm-copy">
            {current ? `${current.position}. В другой группе права другие.` : 'Отметьте официальную группу, чтобы выдать должность.'}
          </p>
        </div>
      </header>
      <div className="realm-body">
        <nav className="realm-rail" aria-label="Разделы группы">
          {tabs.map((item) => (
            <button key={item.id} type="button" className={activeTab === item.id && !chapter ? 'is-on' : ''} onClick={() => { setChapter(false); setTab(item.id) }}>
              {item.label}
            </button>
          ))}
        </nav>
        <main className="realm-main">
          {error && (
            <div className="gate-recover" role="alert">
              <p className="realm-alert">{error}</p>
              <button type="button" className="gate-text" onClick={() => loadSummary(chatId)}>Повторить</button>
            </div>
          )}
          {notice && <p className="realm-note" role="status">{notice}</p>}
          {entryKey && (
            <p className="realm-alert">Личный ключ, один показ: {entryKey}</p>
          )}
          {loading && (
            <div className="realm-load" role="status">
              <span />
              <p>Сверка группы</p>
            </div>
          )}

          {chapter && isCreator && (
            <section>
              <h2 className="realm-h">Администраторы</h2>
              <p className="realm-copy">Должность ниже создателя группы. Одобрить выше запрошенного нельзя. Отказ без причины не сохраняется.</p>
              <form className="realm-form" onSubmit={appoint}>
                <label>Id человека<input inputMode="numeric" value={appointUser} onChange={(e) => setAppointUser(e.target.value)} /></label>
                <label>
                  Должность
                  <select value={appointPos} onChange={(e) => setAppointPos(e.target.value)}>
                    <option value="">Выберите</option>
                    {positions.filter((p) => p.rank < 5).map((p) => (
                      <option key={p.id} value={p.id}>{p.title}</option>
                    ))}
                  </select>
                </label>
                <label>Причина<input value={appointReason} onChange={(e) => setAppointReason(e.target.value)} placeholder="После отказа или сразу" /></label>
                <button type="submit" className="realm-back">Назначить</button>
              </form>
              <h3 className="realm-subhead">Заявки</h3>
              <ul className="realm-list">
                {apps.map((item) => (
                  <li key={item.id}>
                    <div className="realm-row">
                      <strong>{item.group} · {item.position}</strong>
                      <span>{item.userId}</span>
                    </div>
                    <p className="realm-reason">{item.body}</p>
                    <div className="realm-actions">
                      <button type="button" onClick={() => decide(item, true)}>Одобрить</button>
                      <button type="button" onClick={() => decide(item, false)}>Отказать</button>
                    </div>
                  </li>
                ))}
              </ul>
              {apps.length === 0 && <p className="realm-copy">Ожидающих заявок нет.</p>}
            </section>
          )}

          {!chapter && activeTab === 'overview' && (
            <section>
              <p className="realm-hero-num">{fmt(summary?.messages30d)}</p>
              <p className="realm-copy">{chatId ? 'Сообщений за 30 дней в этом чате' : 'Группа не выбрана'}</p>
              {groups.length > 0 && (
                <ul className="realm-list">
                  {groups.map((group) => (
                    <li key={group.chatId}>
                      <button type="button" className={group.chatId === chatId ? 'is-on' : ''} onClick={() => { setChapter(false); setChatId(group.chatId) }}>
                        <strong>{group.title}</strong>
                        <span>{group.position}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {isCreator && (
                <form className="realm-search" onSubmit={onSearch}>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Найти чат и сделать официальным" aria-label="Найти группу" />
                  <button type="submit">Найти</button>
                </form>
              )}
              <ul className="realm-list">
                {hits.map((row) => (
                  <li key={row.chat_id}>
                    <button type="button" onClick={() => makeOfficial(row)}>
                      <strong>{row.name || row.chat_id}</strong>
                      <span>сделать официальной</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!chapter && activeTab === 'people' && (
            <section>
              <h2 className="realm-h">Кто пишет</h2>
              <ul className="realm-list">
                {(summary?.writers || []).map((person) => (
                  <li key={person.user_id}>
                    <button type="button" className="realm-row" onClick={() => setUserId(String(person.user_id))}>
                      <strong>{person.name}</strong>
                      <span>{fmt(person.messages)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              {allowedActions.length > 0 && chatId && (
                <form className="realm-form" onSubmit={punish}>
                  <label>Id человека<input inputMode="numeric" value={userId} onChange={(e) => setUserId(e.target.value)} /></label>
                  <div className="realm-actions">
                    {allowedActions.map((item) => (
                      <button key={item.id} type="button" className={selectedAction?.id === item.id ? 'is-on' : ''} onClick={() => setAction(item.id)}>
                        {item.label}
                      </button>
                    ))}
                  </div>
                  {selectedAction?.needsUntil && (
                    <label>Часы<input inputMode="decimal" value={hours} onChange={(e) => setHours(e.target.value)} /></label>
                  )}
                  <label>Причина<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
                  <p className="realm-copy">Наказание проходит, только если человек младше вашей должности в этой группе. Старшего и равного система не пропустит.</p>
                  <button type="submit" className="realm-back" disabled={acting}>{acting ? 'Запись…' : 'Выполнить'}</button>
                </form>
              )}
            </section>
          )}

          {!chapter && activeTab === 'archive' && (
            <section>
              <h2 className="realm-h">Архив чата</h2>
              {mods && (
                <p className="realm-copy">
                  За 30 дней {fmt(mods.actions30d)} · муты {fmt(mods.mutes)} · баны {fmt(mods.bans)} · кики {fmt(mods.kicks)} · варны {fmt(mods.warns)}
                </p>
              )}
              <ul className="realm-list">
                {(mods?.recent || []).map((row, index) => (
                  <li key={`${row.at}-${index}`}>
                    <div className="realm-row">
                      <strong>{row.action} · {row.target_user_id}</strong>
                      <span>{when(row.at)}</span>
                    </div>
                    {row.reason ? <p className="realm-reason">{row.reason}</p> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!chapter && activeTab === 'analytics' && (
            <section>
              <p className="realm-hero-num">{fmt(summary?.messages30d)}</p>
              <p className="realm-copy">Сообщений за 30 дней · писали {fmt(summary?.writers30d)} · в базе участников {fmt(summary?.members)}</p>
            </section>
          )}

          {!chapter && activeTab === 'more' && (
            <section className="realm-more">
              <button type="button" className="realm-row" onClick={onLeave}><strong>К дверям</strong><span>Другой контур</span></button>
              <a className="realm-row" href="https://t.me/CuteRules" target="_blank" rel="noreferrer"><strong>Правила</strong><span>t.me/CuteRules</span></a>
              {isCreator && (
                <button type="button" className="realm-row" onClick={openCreator}><strong>Администраторы</strong><span>Назначить и разобрать заявки</span></button>
              )}
              {!portrait?.staffCanEnter && (
                <button type="button" className="realm-row is-locked" onClick={() => setLockOpen(true)}>
                  <strong>Панель сотрудника</strong><span>Закрыто</span>
                </button>
              )}
            </section>
          )}
        </main>
      </div>
      <nav className="realm-tabbar" aria-label="Разделы">
        {tabs.map((item) => (
          <button key={item.id} type="button" className={activeTab === item.id && !chapter ? 'is-on' : ''} onClick={() => { setChapter(false); setTab(item.id) }}>
            {item.label}
          </button>
        ))}
      </nav>
      {lockOpen && (
        <div className="firstrun" role="dialog" aria-modal="true">
          <div className="firstrun-sheet">
            <h2 className="firstrun-title">Вы администратор группы, а не сотрудник проекта</h2>
            <p className="firstrun-body">Панель сотрудников Эпсилона открыта только команде проекта.</p>
            <div className="firstrun-actions">
              <button type="button" className="firstrun-skip" onClick={() => setLockOpen(false)}>Понятно</button>
              <button type="button" className="firstrun-next" onClick={() => { setLockOpen(false); onStaffApply?.() }}>Заявка в команду</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
