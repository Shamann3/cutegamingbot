import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  appointGroupAdmin,
  decideGroupApplication,
  fetchGroupApplications,
  fetchGroupPositions,
  fetchGroupSummary,
  groupRealmAct,
  markGroupOfficial,
  saveGroupPosition,
  searchGroupsStudio,
} from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { punishmentHours } from '../lib/gateRecovery'
import FirstRun, { groupSteps, firstRunSeen } from '../components/FirstRun'
import PositionEditor from '../components/PositionEditor'
import useDrawerSwipe from '../lib/useDrawerSwipe'
import { useIsPhone } from '../lib/useIsDesktop'

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

function roomLine(summary) {
  const messages = summary?.messages30d
  const writers = summary?.writers30d
  if (messages == null) return 'За 30 дней цифр ещё нет.'
  if (Number(messages) === 0) return 'За 30 дней в этом чате тишина.'
  if (writers && Number(writers) > 0 && Number(messages) / Number(writers) >= 30) {
    return 'Сообщений много, а пишут не все. Смотрите, кто сверху списка.'
  }
  return 'Чат говорит. Ниже те, кто пишет чаще.'
}

function tabsFor(rights, isCreator) {
  const has = (key) => isCreator || rights.has(key)
  const items = [{ id: 'overview', label: 'Обзор' }]
  if (has('view_members') || [...rights].some((item) => item.startsWith('punish_'))) {
    items.push({ id: 'people', label: 'Люди' })
  }
  if (has('view_archive')) items.push({ id: 'archive', label: 'Архив' })
  if (has('view_analytics')) items.push({ id: 'analytics', label: 'Аналитика' })
  if (has('manage_positions')) items.push({ id: 'rights', label: 'Права' })
  items.push({ id: 'more', label: 'Ещё' })
  return items
}

export default function GroupShell({ portrait, onLeave, onStaffApply }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const isCreator = Boolean(portrait?.isOwner)
  const groups = portrait?.groups || []
  const [chatId, setChatId] = useState(groups[0]?.chatId ?? null)
  const current = groups.find((group) => group.chatId === chatId) || null
  const rights = useMemo(() => new Set(current?.rights || []), [current])
  const tabs = useMemo(() => tabsFor(rights, isCreator), [rights, isCreator])
  const [tab, setTab] = useState('overview')
  const [chapter, setChapter] = useState(false)
  const [lockOpen, setLockOpen] = useState(false)
  const [coach, setCoach] = useState(() => !firstRunSeen('epsilon.onboard.group.v4'))
  const [railOpen, setRailOpen] = useState(false)
  const phone = useIsPhone()
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
  const [savingId, setSavingId] = useState(null)

  const activeTab = tabs.some((item) => item.id === tab) ? tab : 'overview'
  const allowedActions = ACTIONS.filter((item) => isCreator || rights.has(item.right))
  const selectedAction = allowedActions.find((item) => item.id === action) || allowedActions[0]

  const closeRail = useCallback(() => setRailOpen(false), [])
  useDrawerSwipe({
    enabled: phone,
    open: railOpen,
    onOpen: () => setRailOpen(true),
    onClose: closeRail,
  })

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

  const loadPositions = useCallback(async (id) => {
    if (!id) return
    try {
      const data = await fetchGroupPositions(id)
      setPositions(data.positions || [])
    } catch (err) {
      setError(err.message || 'Должности не открылись')
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'rights' && chatId) loadPositions(chatId)
  }, [activeTab, chatId, loadPositions])

  const openCreator = async () => {
    setChapter(true)
    setError('')
    try {
      if (chatId) await loadPositions(chatId)
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
        title: row.name || String(row.chat_id),
        username: row.username || '',
        official: true,
      })
      setNotice('Группа официальная. Нажмите «Сменить панель» и зайдите в неё снова, чтобы она появилась в списке.')
      setChatId(row.chat_id)
      setHits([])
    } catch (err) {
      setError(err.message || 'Не удалось отметить группу')
    }
  }

  const punish = async (event) => {
    event.preventDefault()
    const id = Number(userId)
    if (!chatId || !id) {
      setError('Укажите id человека')
      return
    }
    if (!reason.trim()) {
      setError('Нужна причина')
      return
    }
    let until = null
    if (selectedAction?.needsUntil) {
      until = punishmentHours(hours)
      if (until == null) {
        setError('Укажите часы, больше нуля и не дольше года')
        return
      }
    }
    setActing(true)
    setError('')
    try {
      await groupRealmAct({
        chat_id: chatId,
        user_id: id,
        action: selectedAction.id,
        reason: reason.trim(),
        until_sec: until,
      })
      setNotice('Записано в этот чат')
      setReason('')
      await loadSummary(chatId)
    } catch (err) {
      setError(err.message || 'Действие не прошло')
    } finally {
      setActing(false)
    }
  }

  const appoint = async (event) => {
    event.preventDefault()
    if (!chatId || !appointUser.trim() || !appointPos) {
      setError('Нужны id человека и должность')
      return
    }
    setError('')
    try {
      const data = await appointGroupAdmin({
        chat_id: chatId,
        user_id: Number(appointUser),
        position_id: Number(appointPos),
        reason: appointReason.trim(),
      })
      if (data.entryKey) setEntryKey(data.entryKey)
      setNotice('Должность назначена. Ключ показан один раз.')
      setAppointUser('')
      setAppointReason('')
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

  const savePosition = async (row) => {
    setSavingId(row.id)
    setError('')
    try {
      await saveGroupPosition(row.id, { title: row.title.trim(), rights: row.rights || [] })
      setNotice(`Должность «${row.title.trim()}» сохранена`)
      await loadPositions(chatId)
    } catch (err) {
      setError(err.message || 'Должность не сохранилась')
    } finally {
      setSavingId(null)
    }
  }

  const pickTab = (id) => {
    setChapter(false)
    setRailOpen(false)
    setTab(id)
  }

  const mods = summary?.moderation
  const title = summary?.chat?.title || current?.title || 'Группа не выбрана'

  return (
    <div className={`realm-root${personal ? ' is-personal' : ''}`}>
      {coach && (
        <FirstRun storageKey="epsilon.onboard.group.v4" steps={groupSteps(phone)} onDone={() => setCoach(false)} />
      )}
      <header className="realm-top" data-coach="group-head">
        <button type="button" className="realm-back" data-coach="doors" onClick={onLeave}>Сменить панель</button>
        <div>
          <h1>Панель администраторов групп</h1>
          <p className="realm-copy">
            {title}
            {current?.position ? ` · ${current.position}` : ''}
            {chatId ? ` · ${fmt(summary?.messages30d)} сообщений за 30 дней` : ''}
          </p>
          <p className="realm-copy">{chatId ? roomLine(summary) : 'Отметьте официальную группу, чтобы выдать должность.'}</p>
          <p className="realm-copy">
            {phone
              ? 'Кнопки внизу — страницы этой группы. Свайп вправо открывает список, свайп влево плавно закрывает.'
              : 'Слева страницы этой группы. Каждая показывает только этот чат.'}
          </p>
        </div>
      </header>
      <div className="realm-body">
        <nav className="realm-rail" data-coach="tabs" aria-label="Разделы группы">
          {tabs.map((item) => (
            <button key={item.id} type="button" data-coach={item.id} className={activeTab === item.id && !chapter ? 'is-on' : ''} onClick={() => pickTab(item.id)}>
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
          {entryKey && <p className="realm-alert">Личный ключ, один показ: {entryKey}</p>}
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
                <label>Id человека<input inputMode="numeric" value={appointUser} onChange={(event) => setAppointUser(event.target.value)} /></label>
                <label>
                  Должность
                  <select value={appointPos} onChange={(event) => setAppointPos(event.target.value)}>
                    <option value="">Выберите</option>
                    {positions.filter((item) => item.rank < 5).map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </label>
                <label>Зачем<input value={appointReason} onChange={(event) => setAppointReason(event.target.value)} /></label>
                <button type="submit" className="realm-back">Назначить</button>
              </form>
              <ul className="realm-list">
                {apps.map((item) => (
                  <li key={item.id} className="realm-row">
                    <strong>{item.position} · {item.userId}</strong>
                    <span>
                      <button type="button" onClick={() => decide(item, true)}>Одобрить</button>
                      <button type="button" onClick={() => decide(item, false)}>Отказать</button>
                    </span>
                  </li>
                ))}
              </ul>
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
                  <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти чат и сделать официальным" aria-label="Найти группу" />
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
                  <label>Id человека<input inputMode="numeric" value={userId} onChange={(event) => setUserId(event.target.value)} /></label>
                  <div className="realm-actions">
                    {allowedActions.map((item) => (
                      <button key={item.id} type="button" className={selectedAction?.id === item.id ? 'is-on' : ''} onClick={() => setAction(item.id)}>
                        {item.label}
                      </button>
                    ))}
                  </div>
                  {selectedAction?.needsUntil && (
                    <label>Часы<input inputMode="decimal" value={hours} onChange={(event) => setHours(event.target.value)} /></label>
                  )}
                  <label>Причина<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
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
                  <li key={`${row.at || index}-${row.user_id || index}`} className="realm-row">
                    <strong>{row.action} · {row.target_id || row.user_id || '—'}</strong>
                    <span>{when(row.at || row.created_at)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!chapter && activeTab === 'analytics' && (
            <section>
              <h2 className="realm-h">Этот чат</h2>
              <p className="realm-hero-num">{fmt(summary?.messages30d)}</p>
              <p className="realm-copy">{roomLine(summary)}</p>
              <ul className="realm-list">
                <li className="realm-row"><strong>Писали</strong><span>{fmt(summary?.writers30d)}</span></li>
                <li className="realm-row"><strong>Участники в базе</strong><span>{fmt(summary?.members)}</span></li>
                <li className="realm-row"><strong>Наказания за 30 дней</strong><span>{fmt(mods?.actions30d)}</span></li>
              </ul>
            </section>
          )}

          {!chapter && activeTab === 'rights' && (
            <section>
              <h2 className="realm-h">Права должностей</h2>
              <p className="realm-copy">Название и права этой группы. Менять можно должность младше своей. Создателя группы права не теряют.</p>
              <PositionEditor positions={positions} creator={isCreator} onSave={savePosition} savingId={savingId} />
            </section>
          )}

          {!chapter && activeTab === 'more' && (
            <section>
              <h2 className="realm-h">Ещё</h2>
              <ul className="realm-list">
                <li><a className="realm-row" href="https://t.me/CuteRules" target="_blank" rel="noreferrer"><strong>Правила</strong><span>t.me/CuteRules</span></a></li>
                <li><button type="button" className="realm-row" onClick={onLeave}><strong>Сменить панель</strong><span>выбор входа, без выхода из аккаунта</span></button></li>
                {isCreator && (
                  <li><button type="button" className="realm-row" onClick={openCreator}><strong>Администраторы</strong><span>назначить</span></button></li>
                )}
                {!portrait?.staffCanEnter && (
                  <li>
                    <button type="button" className="realm-row is-locked" onClick={() => setLockOpen((open) => !open)}>
                      <strong>Панель сотрудника</strong>
                      <span>закрыта</span>
                    </button>
                    {lockOpen && (
                      <p className="realm-copy">Вы администратор группы, а не сотрудник проекта. Панель сотрудников Эпсилона открыта только команде проекта.</p>
                    )}
                    {onStaffApply && <button type="button" className="realm-back" onClick={onStaffApply}>Заявка в команду</button>}
                  </li>
                )}
              </ul>
            </section>
          )}
        </main>
      </div>

      {phone && !railOpen && (
        <button type="button" className="phone-edge" aria-label="Открыть страницы" onClick={() => setRailOpen(true)} />
      )}
      {phone && (
        <div className={`realm-rail-sheet${railOpen ? ' is-open' : ''}`} role="dialog" aria-label="Страницы группы" aria-hidden={!railOpen} inert={!railOpen}>
          {tabs.map((item) => (
            <button key={item.id} type="button" className={activeTab === item.id ? 'is-on' : ''} onClick={() => pickTab(item.id)}>
              {item.label}
            </button>
          ))}
          <p>Свайп влево плавно закрывает список</p>
        </div>
      )}

      <nav className="realm-tabbar" data-coach="tabs" data-swipe-ignore aria-label="Вкладки группы">
        {tabs.map((item) => (
          <button key={item.id} type="button" data-coach={item.id} className={activeTab === item.id && !chapter ? 'is-on' : ''} onClick={() => pickTab(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
