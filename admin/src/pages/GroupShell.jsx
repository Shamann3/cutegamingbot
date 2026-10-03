import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  appointGroupAdmin,
  checkRealmMember,
  dismissGroupAdmin,
  fetchRightsBoard,
  decideGroupApplication,
  fetchGroupApplications,
  fetchRealmLogs,
  fetchGroupActivity,
  fetchGroupPositions,
  fetchGroupSummary,
  groupRealmAct,
  markGroupOfficial,
  createGroupPosition,
  deleteGroupPosition,
  saveGroupPosition,
  searchGroupsStudio,
} from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { punishmentHours } from '../lib/gateRecovery'
import { applicationPerson } from '../lib/applicationPerson'
import { groupCabinetTabs } from '../lib/panelPreview'
import { DeedMine } from './sections/payroll/DeedPay'
import FirstRun, { groupSteps, coachClosed, restartCoach } from '../components/FirstRun'
import PanelSidebar from '../components/PanelSidebar'
import { PanelPocketTools } from '../components/ExtrasHub'
import PhoneDock from '../components/PhoneDock'
import EliteTopbar from '../components/EliteTopbar'
import PanelBackgroundMusic from '../components/PanelBackgroundMusic'
import PanelDrawerOverlay from '../components/PanelDrawerOverlay'
import AccentAura from '../components/AccentAura'
import AccentPalette from '../components/AccentPalette'
import { MetricSheetProvider, useMetricSheet } from '../components/MetricSheet'
import DarkPick from '../components/DarkPick'
import FocusWindow from '../components/FocusWindow'
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
import { useTabScroll } from '../lib/useTabScroll'
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

export default function GroupShell(props) {
  return (
    <MetricSheetProvider>
      <GroupShellView {...props} />
    </MetricSheetProvider>
  )
}

function GroupShellView({ portrait, onLeave, onStaffApply, preview = false, banner = null }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const metric = useMetricSheet()
  const isCreator = Boolean(portrait?.isOwner)
  const groups = portrait?.groups || []
  const [chatId, setChatId] = useState(groups[0]?.chatId ?? null)
  const current = groups.find((group) => group.chatId === chatId) || null
  const rights = useMemo(() => new Set(current?.rights || []), [current])
  const tabs = useMemo(() => groupCabinetTabs(rights, isCreator), [rights, isCreator])
  const [tab, setTab] = useState('overview')
  const [chapter, setChapter] = useState(false)
  const [lockOpen, setLockOpen] = useState(false)
  const [coach, setCoach] = useState(() => !preview && !coachClosed('epsilon.onboard.group.v4'))
  const [coachRun, setCoachRun] = useState(0)
  const replayCoach = useCallback(() => {
    restartCoach('epsilon.onboard.group.v4')
    setCoachRun((n) => n + 1)
    setCoach(true)
    setRailOpen(false)
  }, [])
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
  const [appointPrefix, setAppointPrefix] = useState('')
  const [termStart, setTermStart] = useState('')
  const [termEnd, setTermEnd] = useState('')
  const [termOpen, setTermOpen] = useState(false)
  const [memberNote, setMemberNote] = useState('')
  const [realmLogs, setRealmLogs] = useState([])
  const [holders, setHolders] = useState([])
  const [savingId, setSavingId] = useState(null)
  const [posQuery, setPosQuery] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newRank, setNewRank] = useState('1')
  const [newKind, setNewKind] = useState('post')
  const [peakHours, setPeakHours] = useState([])

  const activeTab = tabs.some((item) => item.id === tab) ? tab : 'overview'
  const mainRef = useRef(null)
  useTabScroll(mainRef, activeTab)
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
      : item.id === 'rights' || item.id === 'pay'
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

  const chosenPost = positions.find((item) => String(item.id) === String(appointPos)) || null
  const spamPick = chosenPost?.kind === 'spamblock'

  const loadLogs = useCallback(async (id) => {
    if (!id) return
    try {
      const data = await fetchRealmLogs(id)
      setRealmLogs(data.items || [])
    } catch {
      setRealmLogs([])
    }
  }, [])

  const loadHolders = useCallback(async (id) => {
    if (!id) {
      setHolders([])
      return
    }
    try {
      const data = await fetchRightsBoard()
      const group = (data.groups || []).find((item) => Number(item.chatId) === Number(id))
      setHolders(group?.seats || [])
    } catch {
      setHolders([])
    }
  }, [])

  useEffect(() => {
    if (!isCreator || !chatId) return undefined
    if (chapter) loadLogs(chatId)
    if (chapter || activeTab === 'rights') loadHolders(chatId)
    return undefined
  }, [chapter, activeTab, isCreator, chatId, loadLogs, loadHolders])

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
    if (spamPick && !termEnd) {
      setTermOpen(true)
      setError('Для спам-блока укажите, по какое число он действует')
      return
    }
    setError('')
    try {
      const data = await appointGroupAdmin({
        chat_id: chatId,
        user_id: uid,
        position_id: Number(appointPos),
        reason: appointReason.trim(),
        prefix: appointPrefix.trim(),
        term_start: spamPick ? termStart : '',
        term_end: spamPick ? termEnd : '',
      })
      if (data.entryKey) setEntryKey(data.entryKey)
      setNotice(data.telegram ? `Должность назначена. ${data.telegram}` : 'Должность назначена. Ключ показан один раз.')
      setAppointUser('')
      setAppointUserId(null)
      setAppointReason('')
      setAppointPrefix('')
      setTermStart('')
      setTermEnd('')
      setTermOpen(false)
      setMemberNote('')
      await loadLogs(chatId)
      await loadHolders(chatId)
    } catch (err) {
      setError(err.message || 'Назначить не удалось')
    }
  }

  const dismissHolder = async (person) => {
    const name = person.name || person.userId
    if (!window.confirm(`Снять должность «${person.position}» с ${name}? Человек останется в группе обычным участником, префикс в чате снимется.`)) return
    setError('')
    try {
      const data = await dismissGroupAdmin({ chat_id: chatId, user_id: person.userId })
      setNotice(data.telegram || 'Должность снята. Префикс в группе убран, из чата человек не исключён.')
      await loadHolders(chatId)
      await loadLogs(chatId)
    } catch (err) {
      setError(err.message || 'Снять должность не удалось')
    }
  }

  const lookUpMember = async () => {
    const uid = Number(appointUserId || String(appointUser).replace(/\D/g, ''))
    if (!chatId || !uid) {
      setMemberNote('Сначала выберите человека')
      return
    }
    setMemberNote('Смотрим ответ Telegram…')
    try {
      const data = await checkRealmMember(chatId, uid)
      setMemberNote(data.note || 'Telegram ничего не добавил')
      if (data.until) setTermEnd(data.until)
    } catch (err) {
      setMemberNote(err.message || 'Проверка не ответила')
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
        rank: newKind === 'post' ? Number(newRank) : 0,
        kind: newKind,
        rights: newKind === 'spamblock' ? [] : ['view_members'],
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

  const removePosition = async (row) => {
    const data = await deleteGroupPosition(row.id)
    const tail = data?.telegram ? ` ${data.telegram}` : ' Люди остаются в группе.'
    setEntryKey('')
    setNotice(`Должность «${row.title}» удалена.${tail}`)
    try {
      await loadPositions(chatId)
      await loadHolders(chatId)
    } catch {
      /* должность уже снята */
    }
  }

  const appointHere = async (row, fields) => {
    const data = await appointGroupAdmin({
      chat_id: Number(chatId),
      user_id: fields.userId,
      position_id: row.id,
      reason: fields.reason || '',
      prefix: fields.prefix || '',
      term_start: fields.termStart || '',
      term_end: fields.termEnd || '',
    })
    if (data?.entryKey) setEntryKey(data.entryKey)
    setNotice(data?.telegram || `Должность «${row.title}» назначена`)
    try {
      await loadHolders(chatId)
    } catch {
      /* назначение уже записано */
    }
    return data
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
      {banner}
      {!preview && <PanelBackgroundMusic volume={musicVolume} />}
      {coach && (
        <FirstRun
          key={coachRun}
          storageKey="epsilon.onboard.group.v4"
          steps={groupSteps(phone)}
          layoutKey={railOpen ? 1 : 0}
          onStep={onCoachStep}
          onDone={() => setCoach(false)}
        />
      )}
      {!phone && <PanelDrawerOverlay open={railOpen} onClose={closeRail} ms={700} />}
      {!phone && (
        <PanelSidebar
          sections={navSections}
          activeSection={activeTab}
          onNavigate={pickTab}
          onChangeDoor={preview ? undefined : onLeave}
          onExitPreview={preview ? onLeave : undefined}
          mobileOpen={railOpen}
          onClose={closeRail}
          lightMode={lightMode}
          onTogglePerf={() => setLightMode(!lightMode)}
          musicVolume={musicVolume}
          onMusicVolumeChange={setMusicVolume}
          onToggleMusic={toggleMusicMute}
          accent={accent}
          onAccentChange={(next) => setAccent(persistAccent(next))}
          onReplayCoach={replayCoach}
          brandName="Панель группы"
          brandTag={chatId ? title : 'Одна группа'}
        />
      )}
      <main ref={mainRef} className="panel-shell-main">
      <div className="panel-layout panel-layout-page">
        {!phone && (
          <EliteTopbar
            sections={navSections}
            activeSection={activeTab}
            onNavigate={pickTab}
            compact
            showSupport={false}
            where={chatId
              ? `${current?.position ? `${current.position} · ` : ''}${fmt(summary?.messages30d)} сообщений за 30 дней`
              : 'Группа ещё не выбрана. Её отмечает создатель проекта.'}
          />
        )}
        <div className="grp-page nika-page realm-main">
          {phone && activeTab !== 'more' && (
            <div className="panel-appearance">
              <AccentPalette
                value={accent}
                onChange={(next) => setAccent(persistAccent(next))}
              />
            </div>
          )}
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
                <DarkPick
                  label="Должность"
                  value={appointPos}
                  placeholder="Выберите должность"
                  options={positions.filter((item) => item.rank < 5).map((item) => ({
                    value: String(item.id),
                    label: item.title,
                    hint: item.kind === 'spamblock'
                      ? 'без прав, нужен срок'
                      : item.kind === 'member'
                        ? 'ранг 0, как участник'
                        : `ранг ${item.rank}`,
                  }))}
                  onChange={(next) => {
                    setAppointPos(next)
                    const post = positions.find((item) => String(item.id) === next)
                    if (post?.kind === 'spamblock') {
                      setAppointPrefix(post.prefix || 'спам блок')
                      setTermOpen(true)
                    } else if (post?.kind === 'member') {
                      setAppointPrefix('')
                      setTermOpen(false)
                    } else if (post) {
                      setAppointPrefix(post.prefix || String(post.title || '').slice(0, 16))
                      setTermOpen(false)
                    }
                  }}
                />
                {chosenPost?.kind === 'member' ? (
                  <p className="realm-copy">Обычный пользователь: в группе префикс не ставится, админка чата снимается.</p>
                ) : (
                <label>Префикс в чате
                  <input
                    value={appointPrefix}
                    maxLength={16}
                    placeholder={spamPick ? 'спам блок' : 'до 16 символов, можно пусто'}
                    onChange={(event) => setAppointPrefix(event.target.value)}
                  />
                </label>
                )}
                {spamPick && (
                  <p className="realm-copy">
                    Спам-блок не даёт наказаний. В чате человек числится администратором без бана и удаления — иначе Telegram не пускает писать. Срок задаётся в окне, по окончании должность снимается сама.
                  </p>
                )}
                <label>для чего?<input value={appointReason} onChange={(event) => setAppointReason(event.target.value)} /></label>
                {spamPick && (
                  <button type="button" className="realm-back" onClick={() => setTermOpen(true)}>
                    {termEnd ? `Срок до ${termEnd}` : 'Задать срок спам-блока'}
                  </button>
                )}
                <button type="submit" className="realm-back">Назначить</button>
              </form>
              <div className="staff-ga-seats">
                <h3 className="realm-h">Сейчас на должностях</h3>
                <p className="realm-copy">Снятие оставляет человека в группе без должности и убирает префикс в чате.</p>
                {holders.length === 0 && <p className="realm-copy">В этой группе должностей ни у кого нет.</p>}
                <ul className="realm-list">
                  {holders.map((person) => (
                    <li key={person.userId} className="realm-row staff-ga-person">
                      <strong>{person.name || person.userId}{person.username ? ` · @${person.username}` : ''}</strong>
                      <span>{person.position}{person.prefix ? ` · «${person.prefix}»` : ''}{person.termEnd ? ` · до ${person.termEnd}` : ''}</span>
                      <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => dismissHolder(person)}>
                        Снять должность
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              {termOpen && spamPick && (
                <FocusWindow
                  title="Срок спам-блока"
                  subtitle="Прав на наказания нет. Пока срок идёт, человек может писать в чат. Когда дата конца пройдёт, должность снимется сама, запись попадёт в журнал ниже."
                  onClose={() => setTermOpen(false)}
                >
                  <div className="realm-form">
                    <p className="realm-copy">Telegram не сообщает дату глобального спам-блока. Кнопка ниже показывает только ограничение этого чата, если оно есть. Дату конца подтверждаете вы.</p>
                    <label>С какого числа
                      <input type="date" value={termStart} onChange={(event) => setTermStart(event.target.value)} />
                    </label>
                    <label>По какое число
                      <input type="date" value={termEnd} onChange={(event) => setTermEnd(event.target.value)} />
                    </label>
                    <label>Префикс
                      <input value={appointPrefix} maxLength={16} onChange={(event) => setAppointPrefix(event.target.value)} />
                    </label>
                    <button type="button" className="realm-back" onClick={lookUpMember}>Проверить ответ Telegram</button>
                    {memberNote && <p className="realm-note" role="status">{memberNote}</p>}
                    <button type="button" className="realm-back" disabled={!termEnd} onClick={() => setTermOpen(false)}>
                      {termEnd ? 'Срок записан в форму' : 'Нужна дата конца'}
                    </button>
                  </div>
                </FocusWindow>
              )}
              <h3 className="realm-h">Журнал должностей</h3>
              <p className="realm-copy">Сюда само пишется снятие спам-блока, когда срок вышел. Назначение и смена префикса тоже остаются здесь.</p>
              {realmLogs.length === 0 && <p className="realm-copy">Записей пока нет.</p>}
              <ul className="realm-list">
                {realmLogs.map((item) => (
                  <li key={item.id} className="realm-row">
                    <strong>{item.action === 'spamblock_expired' ? 'Спам-блок снят' : item.action === 'position_removed' ? 'Должность снята' : item.action === 'prefix' ? 'Префикс' : item.action === 'position_created' ? 'Новая должность' : 'Назначение'}</strong>
                    <span>{item.detail}{item.userId ? ` · ${item.userId}` : ''}</span>
                  </li>
                ))}
              </ul>
              <ul className="realm-list">
                {apps.map((item) => {
                  const person = applicationPerson(item)
                  return (
                  <li key={item.id} className="realm-row">
                    <strong>{person.title}{person.username ? ` · @${person.username}` : ''}</strong>
                    <span>{item.position} · id {item.userId}</span>
                    <span>
                      <button type="button" onClick={() => decide(item, true)}>Одобрить</button>
                      <button type="button" onClick={() => decide(item, false)}>Отказать</button>
                    </span>
                  </li>
                  )
                })}
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
              {isCreator && (
              <form className="realm-form" onSubmit={createPosition}>
                <h3 className="realm-h">Новая должность</h3>
                <p className="realm-copy">Создаёт только создатель проекта. Обычный пользователь и спам-блок встают на ранг 0 и не получают наказаний.</p>
                <label>Название<input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} /></label>
                <DarkPick
                  label="Тип"
                  value={newKind}
                  options={[
                    { value: 'post', label: 'Обычная должность', hint: 'права настраиваются отдельно' },
                    { value: 'member', label: 'Обычный пользователь', hint: 'ранг 0, только писать' },
                    { value: 'spamblock', label: 'Спам-блок', hint: 'ранг 0, без прав, со сроком' },
                  ]}
                  onChange={setNewKind}
                />
                {newKind === 'post' && (
                  <label>Ранг, от 0 до 4. Ноль — как участник.
                    <input inputMode="numeric" value={newRank} onChange={(event) => setNewRank(event.target.value.replace(/[^\d]/g, '').slice(0, 1))} />
                  </label>
                )}
                <button type="submit" className="realm-back" disabled={newTitle.trim().length < 2}>Создать должность</button>
              </form>
              )}
              <PositionEditor
                positions={positions.filter((row) => String(row.title || '').toLowerCase().includes(posQuery.trim().toLowerCase()))}
                creator={isCreator}
                chatId={chatId}
                seats={holders}
                onSave={savePosition}
                onDelete={isCreator ? removePosition : null}
                onAppoint={isCreator ? appointHere : null}
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

          {!chapter && activeTab === 'pay' && (
            <section>
              <h2 className="realm-h">Зарплата</h2>
              <p className="realm-copy">
                Куты за наказания, которые создатель подтвердил. Недельная зарплата команды считается отдельно.
              </p>
              <DeedMine isProjectCreator={isCreator} />
            </section>
          )}

          {!chapter && activeTab === 'more' && (
            <section>
              <h2 className="realm-h">Ещё</h2>
              <ul className="realm-list">
                <li><a className="realm-row" href="https://t.me/CuteRules" target="_blank" rel="noreferrer" onClick={() => window.alert("Внимание: переход может закрыть панель — потом снова войдите в админку.")}><strong>Правила</strong><span>t.me/CuteRules · панель может закрыться</span></a></li>
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
              {phone && (
                <PanelPocketTools
                  accent={accent}
                  onAccentChange={(next) => setAccent(persistAccent(next))}
                  lightMode={lightMode}
                  onTogglePerf={() => setLightMode(!lightMode)}
                  musicVolume={musicVolume}
                  onMusicVolumeChange={setMusicVolume}
                  onToggleMusic={toggleMusicMute}
                  onChangeDoor={preview ? undefined : onLeave}
                  onExitPreview={preview ? onLeave : undefined}
                  onReplayCoach={replayCoach}
                />
              )}
            </section>
          )}
        </div>
      </div>
      </main>
      <PhoneDock
        sections={navSections}
        activeSection={activeTab}
        onNavigate={pickTab}
        menuOpen={!phone && railOpen}
        onOpenMenu={phone ? undefined : () => setRailOpen((open) => !open)}
      />
    </div>
  )
}
