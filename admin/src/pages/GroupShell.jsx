import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  appointGroupAdmin,
  checkRealmMember,
  dismissGroupAdmin,
  disableGroupAccess,
  reissueGroupKey,
  showGroupKey,
  fetchRightsBoard,
  decideGroupApplication,
  fetchGroupApplications,
  fetchRealmLogs,
  fetchGroupPositions,
  fetchGroupPulse,
  fetchGroupSummary,
  groupRealmAct,
  markGroupOfficial,
  createGroupPosition,
  deleteGroupPosition,
  orderGroupPositions,
  saveGroupPosition,
  searchGroupsStudio,
  fetchDeedQueue,
  fetchDeedWork,
} from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { punishmentHours } from '../lib/gateRecovery'
import { spanToSend } from '../lib/spanClock'
import { moderationDelta, samePulse } from '../lib/liveMerge'
import { applicationPerson } from '../lib/applicationPerson'
import { groupCabinetTabs, positionSaveBody } from '../lib/panelPreview'
import { grantedWide } from '../lib/realmRights'
import ApproveSeat from '../components/ApproveSeat'
import CaptchaArchiveNote from '../components/CaptchaArchiveNote'
import PositionSupply from '../components/PositionSupply'
import MySalary from './sections/payroll/MySalary'
import KutRate from './sections/payroll/KutRate'
import { CreatorDeck } from './sections/payroll/CreatorPay'
import WorkDesk from './sections/payroll/WorkDesk'
import FirstRun, { groupSteps, workLessonSteps, coachClosed, restartCoach } from '../components/FirstRun'
import WorkLessonButton from '../components/WorkLessonButton'
import PanelSidebar from '../components/PanelSidebar'
import { PanelPocketTools } from '../components/ExtrasHub'
import PhoneDock from '../components/PhoneDock'
import EliteTopbar from '../components/EliteTopbar'
import PanelBackgroundMusic from '../components/PanelBackgroundMusic'
import PanelDrawerOverlay from '../components/PanelDrawerOverlay'
import AccentAura from '../components/AccentAura'
import AccentPalette from '../components/AccentPalette'
import DarkPick from '../components/DarkPick'
import FocusWindow from '../components/FocusWindow'
import PositionEditor from '../components/PositionEditor'
import ActivityBoard from '../components/ActivityBoard'
import GroupArchive from '../components/GroupArchive'
import PersonPunish from '../components/PersonPunish'
import GroupGuard from '../components/GroupGuard'
import GroupLookupPreview from '../components/GroupLookupPreview'
import UserLookupPreview from '../components/UserLookupPreview'
import { repeatCounts } from '../lib/shiftDesk'
import useDrawerSwipe from '../lib/useDrawerSwipe'
import { useGlobalKeys } from '../lib/useGlobalKeys'
import { useIsPhone, useViewportMode } from '../lib/useIsDesktop'
import { useTabScroll } from '../lib/useTabScroll'
import { useMusicMode } from '../lib/musicMode'
import { playMeme, stopMeme } from '../lib/memeSounds'
import { usePerfMode } from '../lib/perfMode'
import AccessKeySheet from '../components/AccessKeySheet'
import OwnKeyControl from '../components/OwnKeyControl'

const HOME_NAME = {
  mute: 'Мут',
  voice: 'Голос',
  kick: 'Кик',
  warn: 'Варн',
  ban: 'Бан в чате',
}

const ACTIONS = [
  { id: 'mute', label: 'Мут', right: 'punish_mute', needsUntil: true },
  { id: 'unmute', label: 'Снять мут', right: 'punish_mute', needsUntil: false },
  { id: 'voice', label: 'Забрать голос', right: 'punish_voice', needsUntil: true },
  { id: 'unvoice', label: 'Вернуть голос', right: 'punish_voice', needsUntil: false },
  { id: 'kick', label: 'Кикнуть', right: 'punish_kick', needsUntil: false },
  { id: 'warn', label: 'Предупредить', right: 'punish_warn', needsUntil: true },
  { id: 'ban', label: 'Бан', right: 'punish_ban', needsUntil: true },
  { id: 'unban', label: 'Снять бан', right: 'punish_ban', needsUntil: false },
]

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function writersCaption(count) {
  const n = Math.abs(Number(count) || 0)
  const n10 = n % 10
  const n100 = n % 100
  if (n10 === 1 && n100 !== 11) return 'человек писал'
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return 'человека писали'
  return 'человек писали'
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

export default function GroupShell({ portrait, onLeave, onStaffApply, preview = false, banner = null }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const isCreator = Boolean(portrait?.isOwner)
  const isProjectCreator = Boolean(portrait?.isProjectCreator)
  const groups = portrait?.groups || []
  const [chatId, setChatId] = useState(groups[0]?.chatId ?? null)
  const current = groups.find((group) => group.chatId === chatId) || null
  const rights = useMemo(() => new Set(current?.rights || []), [current])
  const tabs = useMemo(
    () => groupCabinetTabs(rights, isCreator, current?.pages, current?.rank),
    [rights, isCreator, current],
  )
  const [tab, setTab] = useState('overview')
  const [workCount, setWorkCount] = useState(0)
  const workBoot = useRef(false)
  const shownTabs = useMemo(() => tabs.map((item) => (
    item.id === 'work' && workCount > 0 ? { ...item, label: `Работа · ${workCount}` } : item
  )), [tabs, workCount])
  useEffect(() => {
    if (preview) return undefined
    if (!tabs.some((item) => item.id === 'work') || workBoot.current) return undefined
    workBoot.current = true
    let alive = true
    const job = isProjectCreator ? fetchDeedQueue({}) : fetchDeedWork()
    job.then((data) => {
      if (!alive) return
      setWorkCount(Number(data?.waiting) || 0)
    }).catch(() => {})
    return () => { alive = false }
  }, [preview, isProjectCreator, tabs])
  useEffect(() => {
    if (!tabs.some((item) => item.id === tab)) setTab('overview')
  }, [tabs, tab])
  const [chapter, setChapter] = useState(false)
  const [lockOpen, setLockOpen] = useState(false)
  const [coach, setCoach] = useState(() => !preview && !coachClosed('epsilon.onboard.group.v4'))

  useEffect(() => {
    if (preview) return
    if (coach) {
      stopMeme()
      return
    }
    playMeme('entered')
  }, [preview, coach])
  const [lesson, setLesson] = useState(false)
  const [coachRun, setCoachRun] = useState(0)
  const replayCoach = useCallback(() => {
    restartCoach('epsilon.onboard.group.v4')
    setLesson(false)
    setCoachRun((n) => n + 1)
    setTab('overview')
    setCoach(true)
    setRailOpen(false)
  }, [])
  const workLessonKey = isProjectCreator ? 'epsilon.lesson.work.creator.v1' : 'epsilon.lesson.work.group.v1'
  const openWorkLesson = useCallback(() => {
    restartCoach(workLessonKey)
    setCoach(false)
    setLesson(true)
    setTab('work')
    setRailOpen(false)
  }, [workLessonKey])
  const [railOpen, setRailOpen] = useState(false)
  const phone = useIsPhone()
  const viewport = useViewportMode()
  const { lightMode, setLightMode } = usePerfMode()
  const { volume: musicVolume, setVolume: setMusicVolume, toggleMute: toggleMusicMute } = useMusicMode()
  const [accent, setAccent] = useState(() => loadStoredAccent())
  const [summary, setSummary] = useState(null)
  const [arrived, setArrived] = useState([])
  const summaryRef = useRef(null)
  const actingRef = useRef(false)
  const arrivedTimer = useRef(0)
  summaryRef.current = summary
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [entryKey, setEntryKey] = useState('')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [userId, setUserId] = useState('')
  const [acting, setActing] = useState(false)
  actingRef.current = acting
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
  const [accessSheet, setAccessSheet] = useState(null)
  const [accessBusy, setAccessBusy] = useState(false)
  const [savingId, setSavingId] = useState(null)
  const [posQuery, setPosQuery] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newKind, setNewKind] = useState('post')
  const [ordering, setOrdering] = useState(false)
  const [punishFor, setPunishFor] = useState('')
  const [seatFor, setSeatFor] = useState(null)

  const activeTab = tabs.some((item) => item.id === tab) ? tab : 'overview'
  const heardTab = useRef(activeTab)
  useEffect(() => {
    const prev = heardTab.current
    heardTab.current = activeTab
    if (preview || coach) return
    if (prev === activeTab) return
    if (activeTab === 'more') playMeme('more')
    if (activeTab === 'activity') playMeme('wake')
  }, [activeTab, preview, coach])
  const mainRef = useRef(null)
  useTabScroll(mainRef, activeTab)
  const allowedActions = useMemo(() => {
    const seat = ACTIONS.filter((item) => rights.has(item.right))
    const have = new Set(seat.map((item) => item.id))
    const extra = (summary?.staffActs || [])
      .filter((item) => item?.scope === 'chat' && item.id && !have.has(item.id))
      .map((item) => ({
        id: item.id,
        label: item.label,
        needsUntil: Boolean(item.needsUntil),
        hint: item.hint || '',
      }))
    return [...seat, ...extra]
  }, [rights, summary])
  const seatWide = useMemo(() => {
    const seat = grantedWide(summary?.wide, rights)
    const have = new Set(seat.map((item) => item.id))
    const extra = (summary?.staffActs || [])
      .filter((item) => item?.scope && item.scope !== 'chat' && item.id && !have.has(item.id))
      .map((item) => ({
        id: item.id,
        label: item.label,
        needsUntil: Boolean(item.needsUntil),
        hint: item.hint || '',
      }))
    return [...seat, ...extra]
  }, [summary, rights])

  const closeRail = useCallback(() => setRailOpen(false), [])
  const hasWork = tabs.some((item) => item.id === 'work')
  const onCoachStep = useCallback((step) => {
    if (step?.openSection) setTab(step.openSection)
    if (phone) return
    setRailOpen(Boolean(step?.openNav))
  }, [phone])
  useEffect(() => {
    if (phone) setRailOpen(false)
  }, [phone])
  useEffect(() => {
    applyAccentToDocument(accent)
  }, [accent])
  const navSections = useMemo(() => shownTabs.map((item) => ({
    id: item.id,
    label: item.label,
    labelRu: item.label,
    group: item.id === 'activity' || item.id === 'archive' || item.id === 'work'
      ? 'people'
      : item.id === 'rights' || item.id === 'pay'
        ? 'team'
        : item.id === 'more' || item.id === 'switches'
          ? 'system'
          : 'overview',
    dockLabel: item.id === 'pay' ? 'Зарплата' : undefined,
  })), [shownTabs])
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

  const showArrived = useCallback((rows) => {
    if (!rows?.length) return
    setArrived(rows)
    window.clearTimeout(arrivedTimer.current)
    arrivedTimer.current = window.setTimeout(() => setArrived([]), 4800)
  }, [])

  useEffect(() => () => window.clearTimeout(arrivedTimer.current), [])

  const loadSummary = useCallback(async (id, { quiet = false } = {}) => {
    if (!id) {
      setSummary(null)
      return
    }
    if (!quiet) {
      setLoading(true)
      setError('')
    }
    try {
      const data = await fetchGroupSummary(id)
      const fresh = moderationDelta(summaryRef.current?.moderation?.recent, data?.moderation?.recent).fresh
      setSummary(data)
      if (fresh.length) showArrived(fresh)
    } catch (err) {
      if (!quiet) setSummary(null)
      setError(err.message || 'Карточка группы не открылась')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [showArrived])

  useEffect(() => { loadSummary(chatId) }, [chatId, loadSummary])

  useEffect(() => {
    if (!chatId) return undefined
    let stop = false
    const tick = async () => {
      if (stop || document.hidden || actingRef.current) return
      const current = summaryRef.current
      if (!current?.moderation) return
      try {
        const data = await fetchGroupPulse(chatId)
        if (stop) return
        const seen = (summaryRef.current?.moderation?.recent || []).reduce(
          (max, row) => Math.max(max, Number(row?.id) || 0),
          0,
        )
        const incoming = (data?.recent || []).reduce(
          (max, row) => Math.max(max, Number(row?.id) || 0),
          0,
        )
        if (incoming < seen) return
        const delta = moderationDelta(summaryRef.current?.moderation?.recent, data?.recent)
        const unchanged = !delta.fresh.length && !delta.changed && samePulse(summaryRef.current?.moderation, data)
        if (unchanged) return
        setSummary((prev) => {
          if (!prev?.moderation) return prev
          const held = (prev.moderation.recent || []).reduce(
            (max, row) => Math.max(max, Number(row?.id) || 0),
            0,
          )
          if (incoming < held) return prev
          const next = moderationDelta(prev.moderation.recent, data?.recent)
          return {
            ...prev,
            moderation: {
              ...prev.moderation,
              actions30d: data?.actions30d,
              mutes: data?.mutes,
              bans: data?.bans,
              warns: data?.warns,
              kicks: data?.kicks,
              recent: next.recent,
              watch: data?.watch ?? prev.moderation.watch,
              captchaRemoved: data?.captchaRemoved ?? prev.moderation.captchaRemoved,
            },
          }
        })
        if (delta.fresh.length) showArrived(delta.fresh)
      } catch {
        /* архив остаётся как был, сверка повторится */
      }
    }
    const first = window.setTimeout(tick, 800)
    const timer = window.setInterval(tick, 2500)
    return () => {
      stop = true
      window.clearTimeout(first)
      window.clearInterval(timer)
    }
  }, [chatId, showArrived])

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

  const lookHolderKey = async (person) => {
    setAccessBusy(true)
    setAccessSheet({ person, step: 'look', key: '', error: '', copy: '' })
    try {
      const data = await showGroupKey(person.userId)
      const entryKey = data?.entryKey || ''
      setAccessSheet({
        person,
        step: 'look',
        key: entryKey,
        error: '',
        copy: entryKey
          ? ''
          : 'Копии этого ключа нет: он выдан до того, как панель стала его хранить. Отключите доступ и выдайте новый — тогда ключ останется у вас.',
      })
    } catch (err) {
      setAccessSheet({
        person,
        step: 'look',
        key: '',
        error: err?.message || 'Ключ не открылся',
        copy: '',
      })
    } finally {
      setAccessBusy(false)
    }
  }

  const confirmHolderAccess = async () => {
    if (!accessSheet || accessSheet.step === 'shown' || accessSheet.step === 'look') return
    const person = accessSheet.person
    setAccessBusy(true)
    setAccessSheet((current) => (current ? { ...current, error: '' } : current))
    try {
      if (accessSheet.step === 'off') {
        await disableGroupAccess(person.userId)
        setAccessSheet(null)
      } else {
        const data = await reissueGroupKey(person.userId)
        const entryKey = data?.entryKey || ''
        if (!entryKey) throw new Error('Сервер не вернул ключ')
        setAccessSheet((current) => (current ? { ...current, step: 'shown', key: entryKey, error: '' } : current))
      }
    } catch (err) {
      setAccessSheet((current) => (
        current ? { ...current, error: err?.message || 'Не вышло' } : current
      ))
    } finally {
      setAccessBusy(false)
      if (chatId) loadHolders(chatId).catch(() => {})
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

  const decide = async (item, approve, positionId = null) => {
    const note = approve ? '' : window.prompt('Причина отказа')
    if (!approve && !note) return
    setError('')
    try {
      const data = await decideGroupApplication({
        application_id: item.id,
        approve,
        note: note || '',
        ...(positionId ? { position_id: positionId } : {}),
      })
      if (data.entryKey) setEntryKey(data.entryKey)
      setSeatFor(null)
      setApps((list) => list.filter((row) => row.id !== item.id))
      const placed = data?.position && data?.group ? ` «${data.position}» в «${data.group}».` : ''
      setNotice(approve ? `Заявка одобрена.${placed} Ключ показан один раз.` : 'Заявка отклонена')
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
        rank: newKind === 'post' ? 4 : 0,
        kind: newKind,
        rights: newKind === 'spamblock' ? [] : ['view_members'],
      })
      setNewTitle('')
      setNotice(newKind === 'post'
        ? 'Должность создана и стоит сразу под создателем группы. Отметьте права и сохраните.'
        : 'Должность создана. Она остаётся внизу списка, без ранга администратора.')
      await loadPositions(chatId)
    } catch (err) {
      setError(err.message || 'Должность не создалась')
    }
  }

  const saveOrder = async (ids) => {
    if (!chatId) return
    setOrdering(true)
    setError('')
    try {
      await orderGroupPositions({ chat_id: Number(chatId), ids })
      setNotice('Ранги записаны. Верхняя должность администраторов — ранг 4, ниже по порядку.')
      await loadPositions(chatId)
    } catch (err) {
      setError(err.message || 'Ранги не записались')
      try {
        await loadPositions(chatId)
      } catch {
        /* список останется как был */
      }
    } finally {
      setOrdering(false)
    }
  }

  const savePosition = async (row) => {
    setSavingId(row.id)
    setError('')
    try {
      const data = await saveGroupPosition(row.id, positionSaveBody(row))
      const telegram = /не встал|могла остаться|не обновил/.test(data?.telegram || '') ? ` ${data.telegram}` : ''
      setNotice(`Должность «${row.title.trim()}» сохранена. Вкладки нижней полосы записаны.${telegram}`)
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

  const openPunish = (id) => {
    if (!id) return
    setPunishFor(String(id))
  }

  const mods = summary?.moderation
  const repeats = useMemo(() => repeatCounts(mods?.recent), [mods])
  const canActivity = tabs.some((item) => item.id === 'activity')

  const archiveAct = async ({ userId: raw, action: actId, hours: hrs, untilSec, reason: why }) => {
    const queryText = String(raw || '').trim()
    const asNum = Number(queryText.replace(/^#/, ''))
    const id = Number.isFinite(asNum) && String(asNum) === queryText.replace(/^#/, '') ? asNum : Number(queryText)
    if (!chatId) throw new Error('Сначала выберите группу')
    if (!id || !Number.isFinite(id)) {
      throw new Error('Нужен ID человека. Если его ещё нет в Куте, дождитесь карточки под полем или вставьте числовой ID.')
    }
    if (!String(why || '').trim()) throw new Error('Нужна причина')
    const act = allowedActions.find((item) => item.id === actId)
      || seatWide.find((item) => item.id === actId)
    if (!act) throw new Error('Нет права на это действие')
    let until = null
    if (act.needsUntil) {
      until = untilSec != null ? spanToSend(untilSec) : punishmentHours(hrs)
      if (until == null) {
        throw new Error(untilSec != null
          ? 'Укажите срок больше нуля и не дольше 366 дней'
          : 'Укажите часы, больше нуля и не дольше года')
      }
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
      if (!String(act.id).startsWith('un')) playMeme('punish')
      await loadSummary(chatId, { quiet: true })
    } catch (err) {
      setError(err.message || 'Действие не прошло')
      throw err
    } finally {
      setActing(false)
    }
  }

  const title = summary?.chat?.title || current?.title || 'Группа не выбрана'
  const homeName = !chapter && activeTab === 'overview' && Boolean(chatId)
  const roleLabel = isCreator
    ? (current?.position || 'Создатель')
    : (current?.position || (chatId ? 'Группа' : 'Пусто'))
  const roleClass = roleTone(roleLabel, isCreator)
  const homeMessages = summary?.messages30d
  const homeWriters = summary?.writers30d
  const homePulse = homeMessages != null && homeWriters != null
  const homeLead = (summary?.writers || []).find((row) => row?.name && Number(row.messages) > 0)
  const leadShare = homePulse && homeLead && Number(homeMessages) > 0
    ? Math.round((Number(homeLead.messages) || 0) / Number(homeMessages) * 100)
    : null
  const homeCan = [
    ...allowedActions
      .filter((item) => !String(item.id).startsWith('un'))
      .map((item) => HOME_NAME[item.id] || item.label),
    ...seatWide.map((item) => item.label),
  ]
  const showPulse = Boolean(chatId && canActivity && (summary || (error && !loading)))

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
      {!coach && lesson && hasWork && (
        <FirstRun
          key={`work-${coachRun}`}
          storageKey={workLessonKey}
          steps={workLessonSteps(isProjectCreator ? 'creator' : 'group')}
          layoutKey={railOpen ? 1 : 0}
          onStep={onCoachStep}
          onDone={() => setLesson(false)}
        />
      )}
      {!phone && <PanelDrawerOverlay open={railOpen} onClose={closeRail} ms={700} />}
      <div className="panel-tg-chrome" aria-hidden="true" />
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
      {phone && activeTab !== 'more' && (
        <div className="panel-appearance">
          <AccentPalette
            value={accent}
            onChange={(next) => setAccent(persistAccent(next))}
          />
        </div>
      )}
      <div className="panel-layout panel-layout-page">
        {!phone && (
          <EliteTopbar
            sections={navSections}
            activeSection={activeTab}
            onNavigate={pickTab}
            compact
            showSupport={false}
            where={chatId
              ? `${current?.position ? `${current.position} · ` : ''}${title}`
              : 'Группа ещё не выбрана. Её отмечает создатель проекта.'}
          />
        )}
        <div className="grp-page nika-page realm-main">
          <header className={`nika-head${homeName ? ' is-home-name' : ''}`}>
            {homeName ? (
              <h1 className={`grp-home-title${title.length > 22 ? ' is-long' : ''}`}>
                <span className="grp-home-title-text">{title}</span>
              </h1>
            ) : (
              <div className="nika-head-copy">
                <h1>{shownTabs.find((item) => item.id === activeTab)?.label || (chatId ? title : 'Группа не выбрана')}</h1>
              </div>
            )}
            <div className={`nika-status${chatId ? ' is-ok' : ''}`}>
              <b className={`grp-role-badge is-${roleClass}`}>{roleLabel}</b>
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
              <p className="realm-copy">Должность ниже создателя группы. Если в заявке должность не та, рядом с одобрением есть «Изменить должность»: можно выбрать другую в любой официальной группе. Отказ без причины не сохраняется.</p>
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
                      ? 'ранг 0, нужен срок'
                      : item.kind === 'member' || Number(item.rank) <= 0
                        ? 'ранг 0'
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
                <p className="realm-copy">Отключение закрывает кабинет и гасит старый ключ. Должность остаётся. Снятие убирает должность и префикс, из чата человека не исключает.{portrait?.isProjectCreator ? ' Действующий ключ другого человека открывается кнопкой «Ключ».' : ''}</p>
                {holders.length === 0 && <p className="realm-copy">В этой группе должностей ни у кого нет.</p>}
                <ul className="realm-list">
                  {holders.map((person) => {
                    const isSelf = portrait?.userId != null && person.userId === portrait.userId
                    return (
                    <li key={person.userId} className={`realm-row staff-ga-person${person.accessOff ? ' is-access-off' : ''}`}>
                      <strong>{person.name || person.userId}{person.username ? ` · @${person.username}` : ''}</strong>
                      <span>
                        {person.position}{person.prefix ? ` · «${person.prefix}»` : ''}{person.termEnd ? ` · до ${person.termEnd}` : ''}
                        {person.accessOff ? ' · доступ выключен' : ''}
                      </span>
                      <div className="staff-ga-actions">
                        {isSelf && <OwnKeyControl variant="inline" />}
                        {portrait?.isProjectCreator && !isSelf && !person.accessOff && (
                          <button
                            type="button"
                            className="sec-btn sec-btn-ghost sec-btn-sm"
                            disabled={accessBusy}
                            onClick={() => lookHolderKey(person)}
                          >
                            Ключ
                          </button>
                        )}
                        {!isSelf && !person.accessOff && (
                          <button
                            type="button"
                            className="sec-btn sec-btn-ghost sec-btn-sm"
                            disabled={accessBusy}
                            onClick={() => setAccessSheet({ person, step: 'off', key: '', error: '' })}
                          >
                            Отключить
                          </button>
                        )}
                        {!isSelf && person.accessOff && (
                          <button
                            type="button"
                            className="sec-btn sec-btn-sm sec-btn-success"
                            disabled={accessBusy}
                            onClick={() => setAccessSheet({ person, step: 'key', key: '', error: '' })}
                          >
                            Выдать ключ
                          </button>
                        )}
                        <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => dismissHolder(person)}>
                          Снять должность
                        </button>
                      </div>
                    </li>
                    )
                  })}
                </ul>
                <AccessKeySheet
                  open={Boolean(accessSheet)}
                  name={accessSheet?.person?.name || (accessSheet ? String(accessSheet.person.userId) : '')}
                  kind="group"
                  step={accessSheet?.step || 'off'}
                  busy={accessBusy}
                  error={accessSheet?.error || ''}
                  issuedKey={accessSheet?.key || ''}
                  copy={accessSheet?.copy || ''}
                  onClose={() => { if (!accessBusy) setAccessSheet(null) }}
                  onConfirm={confirmHolderAccess}
                />
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
              <h3 className="realm-h">Заявки</h3>
              <p className="realm-copy">Все заявки в панель. Сначала те, что ждут решения. Если человек уже на должности, заявка нужна для ключа.</p>
              {apps.length === 0 && <p className="realm-copy">Заявок пока нет.</p>}
              <ul className="realm-list">
                {apps.map((item) => {
                  const person = applicationPerson(item)
                  const waiting = (item.status || 'pending') === 'pending'
                  const status = item.status === 'approved' ? 'Принята' : item.status === 'rejected' ? 'Отклонена' : 'На рассмотрении'
                  return (
                  <li key={item.id} className="realm-row">
                    <strong>{person.title}{person.username ? ` · @${person.username}` : ''}</strong>
                    <span>{item.group ? `${item.group} · ` : ''}{item.position} · {status} · id {item.userId}</span>
                    {item.alreadySeated && waiting && <span>Уже на должности. Заявка нужна, чтобы выдать ключ.</span>}
                    {waiting && (
                      <span>
                        <button type="button" onClick={() => decide(item, true)}>Одобрить</button>
                        <button type="button" onClick={() => { setSeatFor(item); setError('') }}>Изменить должность</button>
                        <button type="button" onClick={() => decide(item, false)}>Отказать</button>
                      </span>
                    )}
                  </li>
                  )
                })}
              </ul>
            </section>
          )}

          {!chapter && activeTab === 'overview' && (
            <section className="grp-home">
              {!chatId && <p className="realm-copy">Группа ещё не выбрана. Её отмечает создатель проекта.</p>}
              {chatId && (
                <div className="grp-seat">
                  <p>Вы — {roleLabel} в этой группе.</p>
                  {homeCan.length > 0 ? (
                    <>
                      <p>Может выдавать только то, что включено у этой должности.</p>
                      <ul className="grp-can" aria-label="Дисциплины этой должности">
                        {homeCan.map((label) => <li key={label}>{label}</li>)}
                      </ul>
                    </>
                  ) : (
                    <p>Наказания у этой должности выключены.</p>
                  )}
                </div>
              )}
              {showPulse && (
                <button type="button" className="grp-pulse" onClick={() => pickTab('activity')}>
                  {homePulse ? (
                    <>
                      <span className="grp-pulse-nums">
                        <span>
                          <strong>{fmt(homeMessages)}</strong>
                          <em>сообщений за 30 дней</em>
                        </span>
                        <span>
                          <strong>{fmt(homeWriters)}</strong>
                          <em>{writersCaption(homeWriters)}</em>
                        </span>
                      </span>
                      {homeLead && (
                        <span className="grp-pulse-lead">
                          Чаще всех — {homeLead.name}{leadShare != null ? `, ${leadShare}% за эти 30 дней` : ''}
                        </span>
                      )}
                    </>
                  ) : (
                    <strong className="grp-pulse-miss">Счётчик за 30 дней сейчас не открылся</strong>
                  )}
                  <span className="grp-pulse-go">
                    Подробный разбор — в активности
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </span>
                </button>
              )}
              {groups.length > 1 && (
                <>
                  <h3 className="realm-h">Ваши группы</h3>
                  <p className="realm-copy">Сейчас открыта отмеченная. Нажмите другую — кабинет переключится на неё.</p>
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
                </>
              )}
            </section>
          )}

          {!chapter && activeTab === 'work' && (
            <section className="work-page">
              {isProjectCreator
                ? <CreatorDeck onCount={setWorkCount} />
                : <WorkDesk onCount={setWorkCount} />}
              <WorkLessonButton onClick={openWorkLesson} />
            </section>
          )}

          {!chapter && activeTab === 'activity' && (
            <section className="grp-activity">
              <p className="realm-copy">Сообщения за выбранный срок, сравнение с прошлым и кто пишет. Имя открывает карточку: сколько сообщений и какие наказания уже были.</p>
              <ActivityBoard
                chatId={chatId}
                repeats={repeats}
                watch={mods?.watch || []}
                canArchive
                onOpenArchive={openPunish}
              />
            </section>
          )}

          {!chapter && activeTab === 'archive' && (
            <section className="grp-archive">
              <p className="realm-copy">
                Наказания этого чата.
                {current?.position ? ` Ваша должность: ${current.position}.` : ''}
                {' '}Снять бан или мут — кнопка на карточке. Новое наказание — форма ниже: без причины оно не уйдёт.
              </p>
              {mods && (
              <p className="realm-copy">
                За 30 дней {fmt(mods.actions30d)} наказаний: муты {fmt(mods.mutes)}, баны {fmt(mods.bans)}, кики {fmt(mods.kicks)}, предупреждения {fmt(mods.warns)}.
              </p>
              )}
              <CaptchaArchiveNote stat={mods?.captchaRemoved} />
              <GroupArchive
                rows={mods?.recent || []}
                repeats={repeats}
                watch={summary ? (mods?.watch ?? null) : undefined}
                actions={allowedActions}
                onAct={archiveAct}
                seedQuery={userId}
                arrived={arrived}
                chatId={chatId}
                onOpenUser={(id) => setUserId(String(id))}
              />
              {acting && <p className="realm-copy">Запись…</p>}
            </section>
          )}

          {!chapter && activeTab === 'rights' && (
            <section>
              <h2 className="realm-h">Права должностей</h2>
              <p className="realm-copy">У должности два блока наказаний. «Наказания в этом чате» остаются в этой группе. «Наказания шире этого чата» — отдельные кнопки: все официальные группы или весь проект. Выключено — кнопки нет. Ранг 0 настраивается так же. Наказать можно только того, кто младше.</p>
              <label className="realm-field">Найти должность
                <input value={posQuery} onChange={(event) => setPosQuery(event.target.value)} placeholder="Название" />
              </label>
              {isCreator && (
              <>
              <form className="realm-form" onSubmit={createPosition}>
                <h3 className="realm-h">Новая должность</h3>
                <p className="realm-copy">Создаёт только создатель проекта. Обычная должность встаёт сразу под создателем группы, на ранг 4. Обычный пользователь и спам-блок остаются на ранге 0: сразу могут писать или ждать срок, а остальные права включаются в карточке.</p>
                <label>Название<input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} /></label>
                <DarkPick
                  label="Тип"
                  value={newKind}
                  options={[
                    { value: 'post', label: 'Обычная должность', hint: 'сразу под создателем группы, ранг 4' },
                    { value: 'member', label: 'Обычный пользователь', hint: 'ранг 0, сразу может писать, остальные права в карточке' },
                    { value: 'spamblock', label: 'Спам-блок', hint: 'ранг 0, права в карточке, нужен срок' },
                  ]}
                  onChange={setNewKind}
                />
                <button type="submit" className="realm-back" disabled={newTitle.trim().length < 2}>Создать должность</button>
              </form>
              <PositionSupply
                chatId={chatId}
                onPlaced={async (text) => {
                  setNotice(text)
                  await loadPositions(chatId)
                }}
                />
              </>
              )}
              <PositionEditor
                positions={positions.filter((row) => String(row.title || '').toLowerCase().includes(posQuery.trim().toLowerCase()))}
                creator={isCreator || isProjectCreator}
                chatId={chatId}
                seats={holders}
                onSave={savePosition}
                onDelete={isCreator ? removePosition : null}
                onAppoint={isCreator ? appointHere : null}
                savingId={savingId}
                onOrder={isCreator ? saveOrder : null}
                ordering={ordering}
                canReorder={isCreator && !posQuery.trim()}
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
              <MySalary />
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
              {isProjectCreator && <KutRate />}
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
      {seatFor && (
        <ApproveSeat
          item={seatFor}
          error={error}
          onClose={() => setSeatFor(null)}
          onApprove={(positionId) => decide(seatFor, true, positionId)}
        />
      )}
      {punishFor && (
        <PersonPunish
          chatId={chatId}
          userId={punishFor}
          actions={allowedActions}
          wide={seatWide}
          onAct={archiveAct}
          watch={mods?.watch || []}
          onClose={() => setPunishFor('')}
        />
      )}
    </div>
  )
}
