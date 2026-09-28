import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  appointGroupAdmin,
  decideGroupApplication,
  fetchGroupApplications,
  fetchGroupActivity,
  fetchGroupPositions,
  fetchGroupSummary,
  groupRealmAct,
  markGroupOfficial,
  createGroupPosition,
  saveGroupPosition,
  searchGroupsStudio,
} from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { punishmentHours } from '../lib/gateRecovery'
import FirstRun, { groupSteps, coachClosed } from '../components/FirstRun'
import PanelSidebar, { SettingsControls } from '../components/PanelSidebar'
import AccentPalette from '../components/AccentPalette'
import PhoneDock from '../components/PhoneDock'
import EliteTopbar from '../components/EliteTopbar'
import PanelBackgroundMusic from '../components/PanelBackgroundMusic'
import PanelDrawerOverlay from '../components/PanelDrawerOverlay'
import AccentAura from '../components/AccentAura'
import { MetricSheetProvider, useMetricSheet } from '../components/MetricSheet'
import PositionEditor from '../components/PositionEditor'
import ActivityBoard from '../components/ActivityBoard'
import GroupArchive from '../components/GroupArchive'
import ShiftDesk from '../components/ShiftDesk'
import GroupGuard from '../components/GroupGuard'
import GroupLookupPreview from '../components/GroupLookupPreview'
import UserLookupPreview from '../components/UserLookupPreview'
import { repeatCounts } from '../lib/shiftDesk'
import useDrawerSwipe from '../lib/useDrawerSwipe'
import { useGlobalKeys } from '../lib/useGlobalKeys'
import { useIsPhone, useViewportMode } from '../lib/useIsDesktop'
import { useMusicMode } from '../lib/musicMode'
import { usePerfMode } from '../lib/perfMode'

const ACTIONS = [
  { id: 'mute', label: 'Мут', right: 'punish_mute', needsUntil: true },
  { id: 'unmute', label: 'Размут', right: 'punish_mute', needsUntil: false },
  { id: 'voice', label: 'Голос', right: 'punish_voice', needsUntil: true },
  { id: 'unvoice', label: 'Голос снова', right: 'punish_voice', needsUntil: false },
  { id: 'kick', label: 'Кик', right: 'punish_kick', needsUntil: false },
  { id: 'warn', label: 'Варн', right: 'punish_warn', needsUntil: true },
  { id: 'ban', label: 'Бан', right: 'punish_ban', needsUntil: true },
  { id: 'unban', label: 'Разбан', right: 'punish_ban', needsUntil: false },
]

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function roleTone(title, isCreator) {
  if (isCreator) return 'creator'
  const t = String(title || '').toLowerCase()
  if (t.includes('создател')) return 'creator'
  if (t.includes('админ')) return 'admin'
  if (t.includes('модер')) return 'mod'
  if (t.includes('хелп') || t.includes('help')) return 'help'
  return 'seat'
}

function tabsFor(rights, isCreator) {
  const has = (key) => isCreator || rights.has(key)
  const items = [{ id: 'overview', label: 'Обзор' }]
  if (has('view_members') || has('view_analytics') || [...rights].some((item) => item.startsWith('punish_'))) {
    items.push({ id: 'activity', label: 'Активность' })
  }
  if (has('view_archive')) items.push({ id: 'archive', label: 'Архив' })
  if (has('manage_positions')) items.push({ id: 'rights', label: 'Права' })
  if (isCreator) items.push({ id: 'switches', label: 'Переключатели' })
  items.push({ id: 'more', label: 'Ещё' })
  return items
}

export default function GroupShell(props) {
  return (
    <MetricSheetProvider>
      <GroupShellView {...props} />
    </MetricSheetProvider>
  )
}

function GroupShellView({ portrait, onLeave, onStaffApply }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const metric = useMetricSheet()
  const isCreator = Boolean(portrait?.isOwner)
  const groups = portrait?.groups || []
  const [chatId, setChatId] = useState(groups[0]?.chatId ?? null)
  const current = groups.find((group) => group.chatId === chatId) || null
  const rights = useMemo(() => new Set(current?.rights || []), [current])
  const tabs = useMemo(() => tabsFor(rights, isCreator), [rights, isCreator])
  const [tab, setTab] = useState('overview')
  const [chapter, setChapter] = useState(false)
  const [lockOpen, setLockOpen] = useState(false)
  const [coach, setCoach] = useState(() => !coachClosed('epsilon.onboard.group.v4'))
  const [railOpen, setRailOpen] = useState(false)
  const phone = useIsPhone()
  const viewport = useViewportMode()
  const { lightMode, setLightMode } = usePerfMode()
  const { volume: musicVolume, setVolume: setMusicVolume, toggleMute: toggleMusicMute } = useMusicMode()
  const [accent, setAccent] = useState(() => loadStoredAccent())
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [entryKey, setEntryKey] = useState('')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [userId, setUserId] = useState('')
  const [acting, setActing] = useState(false)
  const [positions, setPositions] = useState([])
  const [apps, setApps] = useState([])
  const [appointUser, setAppointUser] = useState('')
  const [appointUserId, setAppointUserId] = useState(null)
  const [appointPos, setAppointPos] = useState('')
  const [appointReason, setAppointReason] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [posQuery, setPosQuery] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newRank, setNewRank] = useState('1')
  const [peakHours, setPeakHours] = useState([])

  const activeTab = tabs.some((item) => item.id === tab) ? tab : 'overview'
  const allowedActions = ACTIONS.filter((item) => isCreator || rights.has(item.right))

  const closeRail = useCallback(() => setRailOpen(false), [])
  const onCoachStep = useCallback((step) => {
    if (phone) return
    setRailOpen(Boolean(step?.openNav))
  }, [phone])
  useEffect(() => {
    if (phone) setRailOpen(false)
  }, [phone])
  useEffect(() => {
    applyAccentToDocument(accent)
  }, [accent])
  const navSections = useMemo(() => tabs.map((item) => ({
    id: item.id,
    label: item.label,
    labelRu: item.label,
    group: item.id === 'activity' || item.id === 'archive'
      ? 'people'
      : item.id === 'rights'
        ? 'team'
        : item.id === 'more' || item.id === 'switches'
          ? 'system'
          : 'overview',
  })), [tabs])
  useDrawerSwipe({
    enabled: false,
    open: railOpen,
    onOpen: () => setRailOpen(true),
    onClose: closeRail,
  })
  useGlobalKeys({
    onEscape: () => setRailOpen(false),
  })

  useEffect(() => {
    if (!railOpen) return undefined
    const shell = document.querySelector('.panel-shell')
    const prevBody = document.body.style.overflow
    const prevShell = shell instanceof HTMLElement ? shell.style.overflow : ''
    const scrollY = shell instanceof HTMLElement ? shell.scrollTop : 0

    if (phone) {
      document.body.style.overflow = 'hidden'
      if (shell instanceof HTMLElement) {
        shell.style.overflow = 'hidden'
        shell.dataset.navLockScroll = String(scrollY)
      }
    }
    document.documentElement.classList.add('panel-nav-open')

    return () => {
      document.body.style.overflow = prevBody
      document.documentElement.classList.remove('panel-nav-open')
      if (shell instanceof HTMLElement) {
        shell.style.overflow = prevShell
        const y = Number(shell.dataset.navLockScroll || 0)
        delete shell.dataset.navLockScroll
        if (phone) shell.scrollTop = y
      }
    }
  }, [railOpen, phone])

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

  useEffect(() => {
    if (!chatId) {
      setPeakHours([])
      return undefined
    }
    let stop = false
    fetchGroupActivity(chatId, { period: 'week' })
      .then((data) => {
        if (stop || data?.available === false) {
          if (!stop) setPeakHours([])
          return
        }
        const series = Array.isArray(data?.series) ? data.series : []
        const ranked = [...series]
          .map((point) => ({
            date: point.date,
            messages: Number(point.messages) || 0,
            writers: Number(point.writers) || 0,
          }))
          .filter((point) => point.messages > 0)
          .sort((a, b) => b.messages - a.messages)
          .slice(0, 3)
        setPeakHours(ranked)
      })
      .catch(() => {
        if (!stop) setPeakHours([])
      })
    return () => { stop = true }
  }, [chatId])

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
    if ((activeTab === 'rights' || chapter) && chatId) loadPositions(chatId)
  }, [activeTab, chapter, chatId, loadPositions])

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
    event?.preventDefault?.()
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

  const appoint = async (event) => {
    event.preventDefault()
    const uid = Number(appointUserId || String(appointUser).replace(/\D/g, ''))
    if (!chatId || !uid || !appointPos) {
      setError('Нужны человек и должность')
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
      if (data.entryKey) setEntryKey(data.entryKey)
      setNotice('Должность назначена. Ключ показан один раз.')
      setAppointUser('')
      setAppointUserId(null)
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

  const createPosition = async (event) => {
    event.preventDefault()
    if (!chatId) return
    setError('')
    try {
      await createGroupPosition({
        chat_id: Number(chatId),
        title: newTitle.trim(),
        rank: Number(newRank),
        rights: ['view_members'],
      })
      setNewTitle('')
      setNotice('Должность создана. Отметьте права наказаний и сохраните.')
      await loadPositions(chatId)
    } catch (err) {
      setError(err.message || 'Должность не создалась')
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
  const repeats = useMemo(() => repeatCounts(mods?.recent), [mods])
  const canActivity = tabs.some((item) => item.id === 'activity')

  const archiveAct = async ({ userId: raw, action: actId, hours: hrs, reason: why }) => {
    const queryText = String(raw || '').trim()
    const asNum = Number(queryText.replace(/^#/, ''))
    const id = Number.isFinite(asNum) && String(asNum) === queryText.replace(/^#/, '') ? asNum : Number(queryText)
    if (!chatId) throw new Error('Сначала выберите группу')
    if (!id || !Number.isFinite(id)) throw new Error('Укажите числовой id или выберите человека из подсказки')
    if (!String(why || '').trim()) throw new Error('Нужна причина')
    const act = allowedActions.find((item) => item.id === actId)
    if (!act) throw new Error('Нет права на это действие')
    let until = null
    if (act.needsUntil) {
      until = punishmentHours(hrs)
      if (until == null) throw new Error('Укажите часы, больше нуля и не дольше года')
    }
    setActing(true)
    setError('')
    try {
      const data = await groupRealmAct({
        chat_id: chatId,
        user_id: id,
        action: act.id,
        reason: String(why).trim(),
        until_sec: until,
      })
      setNotice(data?.receipt || 'Записано в архив официальной группы')
      await loadSummary(chatId)
    } catch (err) {
      setError(err.message || 'Действие не прошло')
      throw err
    } finally {
      setActing(false)
    }
  }

  const title = summary?.chat?.title || current?.title || 'Группа не выбрана'
  const roleLabel = isCreator
    ? (current?.position || 'Создатель')
    : (current?.position || (chatId ? 'Группа' : 'Пусто'))
  const roleClass = roleTone(roleLabel, isCreator)

  return (
    <div className={`panel-shell panel-shell-${viewport}${personal ? ' is-personal' : ''}`} data-viewport={viewport}>
      <AccentAura />
      <PanelBackgroundMusic volume={musicVolume} />
      {coach && (
        <FirstRun
          storageKey="epsilon.onboard.group.v4"
          steps={groupSteps(phone)}
          layoutKey={railOpen ? 1 : 0}
          onStep={onCoachStep}
          onDone={() => setCoach(false)}
        />
      )}
      <PanelDrawerOverlay open={railOpen} onClose={closeRail} ms={700} />
      <main className="panel-shell-main">
      <div className="panel-layout panel-layout-page">
        <PanelSidebar
          sections={navSections}
          activeSection={activeTab}
          onNavigate={pickTab}
          onChangeDoor={onLeave}
          mobileOpen={railOpen}
          onClose={closeRail}
          lightMode={lightMode}
          onTogglePerf={() => setLightMode(!lightMode)}
          musicVolume={musicVolume}
          onMusicVolumeChange={setMusicVolume}
          onToggleMusic={toggleMusicMute}
          accent={accent}
          onAccentChange={(next) => setAccent(persistAccent(next))}
          brandName="Панель группы"
          brandTag={chatId ? title : 'Одна группа'}
        />
        {!phone && (
          <EliteTopbar
            sections={navSections}
            activeSection={activeTab}
            onNavigate={pickTab}
            onOpenMenu={() => setRailOpen((open) => !open)}
            menuOpen={railOpen}
            compact
            showSupport={false}
            where={chatId
              ? `${current?.position ? `${current.position} · ` : ''}${fmt(summary?.messages30d)} сообщений за 30 дней`
              : 'Группа ещё не выбрана. Её отмечает создатель проекта.'}
          />
        )}
        <div className="grp-page nika-page realm-main">
          <header className="nika-head">
            <div className="nika-head-copy">
              <h1>{tabs.find((item) => item.id === activeTab)?.label || (chatId ? title : 'Группа не выбрана')}</h1>
              {!phone && (
                <p>Страницы внизу экрана. Меню — кнопка с ползунками в доке.</p>
              )}
            </div>
            <div className={`nika-status${chatId ? ' is-ok' : ''}`}>
              <b className={`grp-role-badge is-${roleClass}`}>{roleLabel}</b>
              <span>{chatId ? `${fmt(summary?.messages30d)} за 30 дней` : 'её отмечает создатель'}</span>
            </div>
          </header>
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
            <section className="grp-appoint">
              <h2 className="realm-h">Администраторы</h2>
              <p className="realm-copy">Должность ниже создателя группы. Одобрить выше запрошенного нельзя. Отказ без причины не сохраняется.</p>
              <form className="realm-form grp-appoint-form" onSubmit={appoint}>
                <UserLookupPreview
                  value={appointUser}
                  onChange={(v) => { setAppointUser(v); setAppointUserId(null) }}
                  onResolved={(u) => setAppointUserId(u?.userId ?? u?.user_id ?? null)}
                  placeholder="ID, @username или имя"
                  label="Человек"
                />
                <label className="grp-appoint-pos">
                  Должность
                  <select value={appointPos} onChange={(event) => setAppointPos(event.target.value)}>
                    <option value="">Выберите</option>
                    {positions.filter((item) => item.rank < 5).map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </label>
                <label>для чего?<input value={appointReason} onChange={(event) => setAppointReason(event.target.value)} /></label>
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
              <div className="act-bento grp-overview-stats">
                <button type="button" className="is-on metric-tile" onClick={() => metric.open({
                  id: 'grp-writers',
                  title: 'Активные за 30 дней',
                  value: fmt(summary?.writers30d ?? summary?.members),
                  hint: 'Участники, которые писали в этот чат',
                  action: canActivity ? { label: 'Открыть активность', run: () => pickTab('activity') } : null,
                })}>
                  <strong>{fmt(summary?.writers30d ?? summary?.members)}</strong>
                  <span>активных за 30 дней</span>
                </button>
                <button type="button" className="metric-tile" onClick={() => metric.open({
                  id: 'grp-messages',
                  title: 'Сообщения за 30 дней',
                  value: fmt(summary?.messages30d),
                  hint: 'Все сообщения этого чата',
                  action: canActivity ? { label: 'Открыть активность', run: () => pickTab('activity') } : null,
                })}>
                  <strong>{fmt(summary?.messages30d)}</strong>
                  <span>сообщений за 30 дней</span>
                </button>
                <button type="button" className="metric-tile" onClick={() => metric.open({
                  id: 'grp-members',
                  title: 'Участники в учёте',
                  value: fmt(summary?.members),
                  hint: 'Сколько человек панель видит в этой группе',
                  action: canActivity ? { label: 'Открыть активность', run: () => pickTab('activity') } : null,
                })}>
                  <strong>{fmt(summary?.members)}</strong>
                  <span>участников в учёте</span>
                </button>
              </div>
              {peakHours.length > 0 && (
                <div className="grp-peak">
                  <h3 className="realm-h">Пиковые дни</h3>
                  <p className="realm-copy">Нажмите — откроется аналитика активности.</p>
                  <div className="realm-actions e-seg">
                    {peakHours.map((point) => (
                      <button
                        key={point.date}
                        type="button"
                        className="is-on metric-tile"
                        onClick={() => metric.open({
                          id: `grp-peak-${point.date}`,
                          title: String(point.date),
                          value: fmt(point.messages),
                          unit: 'сообщений',
                          hint: 'Пиковый день этого чата',
                          action: canActivity ? { label: 'Открыть активность', run: () => pickTab('activity') } : null,
                        })}
                      >
                        {point.date}: {fmt(point.messages)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <ShiftDesk chatId={chatId} canActivity={canActivity} />
              {groups.length > 1 && (
                <ul className="realm-list">
                  {groups.map((group) => (
                    <li key={group.chatId}>
                      <button type="button" className={group.chatId === chatId ? 'is-on' : ''} onClick={() => { setChapter(false); setChatId(group.chatId) }}>
                        <strong>{group.title}</strong>
                        <span className={`grp-role-badge is-${roleTone(group.position, false)}`}>{group.position}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {!chapter && activeTab === 'activity' && (
            <section>
              <h2 className="realm-h">Активность</h2>
              <p className="realm-copy">Живые сообщения этого чата. Клетка — день или месяц. Наказать человека можно во вкладке «Архив».</p>
              <ActivityBoard chatId={chatId} repeats={repeats} onOpenUser={(id) => setUserId(String(id))} />
            </section>
          )}

          {!chapter && activeTab === 'archive' && (
            <section>
              <h2 className="realm-h">Архив чата</h2>
              <p className="realm-copy">
                Официальная группа Кьюта.
                {current?.position ? ` Ваша должность: ${current.position}.` : ''}
                {' '}Наказания и снятие — здесь, с обязательной причиной.
              </p>
              {mods && (
                <p className="realm-copy">
                  За 30 дней {fmt(mods.actions30d)} · муты {fmt(mods.mutes)} · баны {fmt(mods.bans)} · кики {fmt(mods.kicks)} · варны {fmt(mods.warns)}
                </p>
              )}
              <GroupArchive
                rows={mods?.recent || []}
                repeats={repeats}
                watch={summary ? (mods?.watch ?? null) : undefined}
                actions={allowedActions}
                onAct={archiveAct}
                seedQuery={userId}
                onOpenUser={(id) => setUserId(String(id))}
              />
              {acting && <p className="realm-copy">Запись…</p>}
            </section>
          )}

          {!chapter && activeTab === 'rights' && (
            <section>
              <h2 className="realm-h">Права должностей</h2>
              <p className="realm-copy">Страницы кабинета, наказания и права Telegram. Наказать можно только младшего. При правке сравниваем с должностью рангом ниже.</p>
              <label className="realm-field">Найти должность
                <input value={posQuery} onChange={(event) => setPosQuery(event.target.value)} placeholder="Название" />
              </label>
              <form className="realm-form" onSubmit={createPosition}>
                <label>Новая должность<input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} /></label>
                <label>Ранг, от 1 до {isCreator ? 4 : Math.max(1, Number(current?.rank || 1) - 1)}
                  <input inputMode="numeric" value={newRank} onChange={(event) => setNewRank(event.target.value)} />
                </label>
                <button type="submit" className="realm-back" disabled={newTitle.trim().length < 2}>Создать должность</button>
              </form>
              <PositionEditor
                positions={positions.filter((row) => String(row.title || '').toLowerCase().includes(posQuery.trim().toLowerCase()))}
                creator={isCreator}
                onSave={savePosition}
                savingId={savingId}
              />
            </section>
          )}

          {!chapter && activeTab === 'switches' && isCreator && (
            <section>
              <h2 className="realm-h">Переключатели проекта</h2>
              <p className="realm-copy">Все выключатели группы и официальности — в одном месте. Видны только создателю.</p>
              <GroupGuard chatId={chatId} creator={isCreator} />
              <h3 className="realm-h">Официальная группа</h3>
              <p className="realm-copy">Найти чат и отметить официальным для кабинета группы.</p>
              <div className="guard-lookup">
                <GroupLookupPreview
                  value={query}
                  onChange={setQuery}
                  onResolved={(row) => {
                    if (row) setHits([row])
                  }}
                  label="Найти чат"
                  placeholder="Id, @username, ссылка или название"
                />
                <button type="button" className="realm-back" onClick={onSearch}>Найти</button>
              </div>
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

          {!chapter && activeTab === 'more' && (
            <section>
              <h2 className="realm-h">Ещё</h2>
              {phone && (
                <div className="extras-settings">
                  <h2>Настройки</h2>
                  <AccentPalette value={accent} onChange={(next) => setAccent(persistAccent(next))} />
                  <SettingsControls
                    musicVolume={musicVolume}
                    onToggleMusic={toggleMusicMute}
                    onMusicVolumeChange={setMusicVolume}
                    lightMode={lightMode}
                    onTogglePerf={() => setLightMode(!lightMode)}
                  />
                </div>
              )}
              <ul className="realm-list">
                <li><a className="realm-row" href="https://t.me/CuteRules" target="_blank" rel="noreferrer" onClick={() => window.alert("Внимание: переход может закрыть панель — потом снова войдите в админку.")}><strong>Правила</strong><span>t.me/CuteRules · панель может закрыться</span></a></li>
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
        </div>
      </div>
      </main>
      <PhoneDock
        sections={navSections}
        activeSection={activeTab}
        onNavigate={pickTab}
        menuOpen={phone ? false : railOpen}
        onOpenMenu={phone ? undefined : () => setRailOpen((open) => !open)}
      />
    </div>
  )
}
