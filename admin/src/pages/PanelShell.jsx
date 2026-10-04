import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PANEL_SECTIONS, visibleSections, splitDockSections, dockActiveId } from '../constants/panelNav'
import PanelSidebar from '../components/PanelSidebar'
import EliteTopbar from '../components/EliteTopbar'
import ToastHost from '../components/ToastHost'
import {
  fetchAdminMe,
  fetchPrOverview,
  fetchStaffPunishRights,
  fetchDeedQueue,
  fetchStaffWorkCount,
  fetchSupportStats,
  fetchTiktokCounts,
  logoutAdmin,
  registerUnauthorizedHandler,
  setPanelPreviewMode,
} from '../lib/adminClient'
import { setProfileStandIn } from '../lib/adminProfile'
import DashboardSection from './sections/DashboardSection'
import SectionPlaceholder from './sections/SectionPlaceholder'
import UsersSection from './sections/UsersSection'
import AccountsSection from './sections/AccountsSection'
import EconomySection from './sections/EconomySection'
import MarketSection from './sections/MarketSection'
import FarmSection from './sections/FarmSection'
import ContentSection from './sections/ContentSection'
import GiveawaysSection from './sections/GiveawaysSection'
import TikTokSection from './sections/TikTokSection'
import BotQuestsSection from './sections/BotQuestsSection'
import GroupBalanceLevelSection from './sections/GroupBalanceLevelSection'
import GroupsStudioSection from './sections/GroupsStudioSection'
import NikaSection from './sections/NikaSection'
import PrGroupsSection from './sections/PrGroupsSection'
import GamesSection from './sections/GamesSection'
import NikaCrisisStrip from '../components/NikaCrisisStrip'
import SoftRestartSection from './sections/SoftRestartSection'
import AchievementsSection from './sections/AchievementsSection'
import BroadcastSection from './sections/BroadcastSection'
import LogsSection from './sections/LogsSection'
import AnalyticsSection from './sections/AnalyticsSection'
import SystemSection from './sections/SystemSection'
import EventsSection from './sections/EventsSection'
import SecuritySection from './sections/SecuritySection'
import StaffSection from './sections/StaffSection'
import SupportSection from './sections/SupportSection'
import ModerationSection from './sections/ModerationSection'
import ChronicleSection from './sections/ChronicleSection'
import CommandCenterSection from './sections/CommandCenterSection'
import RulesGateModal from '../components/RulesGateModal'
import PanelBackgroundMusic from '../components/PanelBackgroundMusic'
import PanelDrawerOverlay from '../components/PanelDrawerOverlay'
import AccentAura from '../components/AccentAura'
import { MetricSheetProvider } from '../components/MetricSheet'
import { usePerfMode } from '../lib/perfMode'
import { useMusicMode } from '../lib/musicMode'
import { useGlobalKeys } from '../lib/useGlobalKeys'
import {
  applyAccentToDocument,
  loadStoredAccent,
  persistAccent,
} from '../lib/accentTheme'
import { loadRecentSections, pushRecentSection } from '../lib/recentSections'
import { useViewportMode, useIsPhone } from '../lib/useIsDesktop'
import useDrawerSwipe from '../lib/useDrawerSwipe'
import { useTabScroll } from '../lib/useTabScroll'
import GroupGuardDesk from './sections/GroupGuardDesk'
import FirstRun, { staffSteps, workLessonSteps, coachClosed, restartCoach } from '../components/FirstRun'
import StaffDesk from './sections/payroll/StaffDesk'
import { CreatorDeck } from './sections/payroll/CreatorPay'
import WorkLessonButton from '../components/WorkLessonButton'
import PanelPreviewBar from '../components/PanelPreviewBar'
import GroupShell from './GroupShell'
import {
  PREVIEW_FALLBACK_PERMISSIONS,
  enabledPunish,
  previewStandIn,
  previewTitle,
  staffPreviewNav,
} from '../lib/panelPreview'
import PhoneDock from '../components/PhoneDock'
import AccentPalette from '../components/AccentPalette'
import ExtrasHub, { PanelPocketTools } from '../components/ExtrasHub'

export default function PanelShell({ onLogout, onChangeDoor }) {
  const { lightMode, setLightMode } = usePerfMode()
  const { volume: musicVolume, setVolume: setMusicVolume, toggleMute: toggleMusicMute } = useMusicMode()
  const viewport = useViewportMode()
  const phone = useIsPhone()
  const [accent, setAccent] = useState(() => loadStoredAccent())

  useEffect(() => {
    applyAccentToDocument(accent)
  }, [accent])

  const handleAccentChange = useCallback((next) => {
    const saved = persistAccent(next)
    setAccent(saved)
  }, [])

  const [section, setSection] = useState('dashboard')
  const mainRef = useRef(null)
  useTabScroll(mainRef, section)
  const [flashKey, setFlashKey] = useState(0)
  const [usersInitialId, setUsersInitialId] = useState(null)
  const [groupsInitialId, setGroupsInitialId] = useState(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [permissions, setPermissions] = useState([])
  const [panelSections, setPanelSections] = useState(null)
  const [panelTabs, setPanelTabs] = useState(null)
  const [role, setRole] = useState(null)
  const [myUserId, setMyUserId] = useState(null)
  const [needsRules, setNeedsRules] = useState(false)
  const [godMode, setGodMode] = useState(false)
  const [projectCreatorId, setProjectCreatorId] = useState(null)
  const [isProjectCreator, setIsProjectCreator] = useState(false)
  const [canBanfull, setCanBanfull] = useState(false)
  const [staffPerms, setStaffPerms] = useState([])
  const [contentInitialTab, setContentInitialTab] = useState(null)
  const [staffEntry, setStaffEntry] = useState(null)
  const [recentSections, setRecentSections] = useState(() => loadRecentSections())
  const [coach, setCoach] = useState(() => !coachClosed('epsilon.onboard.staff.v4'))
  const [lesson, setLesson] = useState(false)
  const [workCount, setWorkCount] = useState(0)
  const [coachRun, setCoachRun] = useState(0)
  const [preview, setPreview] = useState(null)
  const onCoachStep = useCallback((step) => {
    if (step?.openSection) setSection(step.openSection)
    if (phone) return
    setMobileNavOpen(Boolean(step?.openNav))
  }, [phone])

  useEffect(() => {
    if (phone) setMobileNavOpen(false)
  }, [phone])
  useDrawerSwipe({
    enabled: false,
    open: mobileNavOpen,
    onOpen: () => setMobileNavOpen(true),
    onClose: () => setMobileNavOpen(false),
  })

  useGlobalKeys({
    onEscape: () => setMobileNavOpen(false),
  })

  useEffect(() => {
    if (!mobileNavOpen) return undefined
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
  }, [mobileNavOpen, phone])

  useEffect(() => {
    let cancelled = false
    fetchAdminMe()
      .then((me) => {
        if (cancelled) return
        setPermissions(me.permissions || [])
        setPanelSections(Array.isArray(me.panelSections) ? me.panelSections : null)
        setPanelTabs(me.panelTabs && typeof me.panelTabs === 'object' ? me.panelTabs : null)
        setRole(me.role || null)
        setMyUserId(me.userId || null)
        setProjectCreatorId(me.projectCreatorId ?? null)
        setIsProjectCreator(!!me.isProjectCreator)
        setCanBanfull(!!me.canBanfull)
        setStaffPerms(Array.isArray(me.staffPerms) ? me.staffPerms : [])
        // Окно правил при первом входе - кроме владельца.
        if (me.role !== 'owner' && !me.rulesAcceptedAt) {
          setNeedsRules(true)
        }
      })
      .catch((err) => {
        if (cancelled) return
        // Явный отказ доступа (не админ / сессия недействительна) — вернуть на вход.
        // Обычные сетевые сбои (без статуса) панель не роняют, чтобы не выкидывать
        // владельца из-за кратковременной ошибки связи.
        if (err?.status === 401 || err?.status === 403) {
          logoutAdmin()
          onLogout?.()
        }
      })
    return () => {
      cancelled = true
    }
  }, [onLogout])

  const staffPreview = preview?.kind === 'staff' ? preview : null
  const showCreator = isProjectCreator && !preview
  const viewPermissions = staffPreview ? (staffPreview.permissions || PREVIEW_FALLBACK_PERMISSIONS) : permissions
  const viewRole = staffPreview ? staffPreview.role : role
  const viewUserId = staffPreview ? staffPreview.userId : myUserId
  const viewStaffPerms = staffPreview ? (staffPreview.staffPerms || []) : staffPerms
  const viewBanfull = staffPreview ? viewStaffPerms.includes('banfull') : canBanfull
  const tabsForView = staffPreview ? staffPreview.tabs : panelTabs

  const navSections = useMemo(
    () => (staffPreview
      ? staffPreviewNav(staffPreview, projectCreatorId)
      : visibleSections(permissions, panelSections, role, {
        myUserId,
        projectCreatorId,
        isProjectCreator,
      })),
    [staffPreview, permissions, panelSections, role, myUserId, projectCreatorId, isProjectCreator],
  )

  const replayCoach = useCallback(() => {
    restartCoach('epsilon.onboard.staff.v4')
    setLesson(false)
    setCoachRun((n) => n + 1)
    setSection('dashboard')
    setCoach(true)
    setMobileNavOpen(false)
  }, [])
  const workLessonKey = isProjectCreator && !preview
    ? 'epsilon.lesson.work.creator.v1'
    : 'epsilon.lesson.work.staff.v1'
  const openWorkLesson = useCallback(() => {
    restartCoach(workLessonKey)
    setCoach(false)
    setLesson(true)
    setSection('work')
    setMobileNavOpen(false)
  }, [workLessonKey])

  const openPreview = useCallback((next) => {
    if (!isProjectCreator || !next) return
    setPanelPreviewMode(true)
    setProfileStandIn(previewStandIn(next))
    setPreview(next)
    setCoach(false)
    setMobileNavOpen(false)
    if (next.kind === 'staff') {
      setStaffEntry(null)
      setSection('dashboard')
    }
  }, [isProjectCreator])

  const exitPreview = useCallback(() => {
    const office = preview?.kind === 'group' ? 'group' : 'staff'
    setPanelPreviewMode(false)
    setProfileStandIn(null)
    if (office === 'group') setAccent(loadStoredAccent())
    setPreview(null)
    setStaffEntry({ office, slice: 'view' })
    setSection('staff')
    setMobileNavOpen(false)
  }, [preview])

  useEffect(() => () => {
    setPanelPreviewMode(false)
    setProfileStandIn(null)
  }, [])

  useEffect(() => {
    if (preview?.kind !== 'staff' || preview.staffPerms != null) return undefined
    let stop = false
    const settle = (list) => {
      if (stop) return
      setPreview((current) => (
        current?.kind === 'staff' && current.role === preview.role && current.staffPerms == null
          ? { ...current, staffPerms: list }
          : current
      ))
    }
    fetchStaffPunishRights()
      .then((data) => settle(enabledPunish(data?.roles || [], preview.role) || []))
      .catch(() => settle([]))
    return () => { stop = true }
  }, [preview])

  const { dock: dockSections, extras: extraSections, primaryIds } = useMemo(
    () => splitDockSections(navSections),
    [navSections],
  )
  const showWork = navSections.some((item) => item.id === 'work')

  useEffect(() => {
    if (!showWork || preview || role == null) return undefined
    let alive = true
    const job = isProjectCreator ? fetchDeedQueue({}) : fetchStaffWorkCount()
    job
      .then((data) => { if (alive) setWorkCount(Number(data?.waiting) || 0) })
      .catch(() => {})
    return () => { alive = false }
  }, [showWork, preview, role, isProjectCreator])

  const isMore = section === 'more'

  // Если текущий раздел закрыли в матрице — уводим на первую доступную вкладку.
  useEffect(() => {
    if (!navSections.length) return
    if (section === 'more') return
    if (!navSections.some((s) => s.id === section)) {
      setSection(navSections[0].id)
    }
  }, [navSections, section])

  // Счётчик открытых обращений — питает значок у пункта «Поддержка» и точку
  // на колокольчике. Опрашиваем только когда вкладка на экране, чтобы
  // фоновая панель не долбила API.
  const [openTickets, setOpenTickets] = useState(0)
  const [tiktokPending, setTiktokPending] = useState(0)
  const [nikaCrisisCount, setNikaCrisisCount] = useState(0)
  const [prPending, setPrPending] = useState(0)

  const moreBadge = useMemo(() => {
    const map = { tiktok: tiktokPending, nika: nikaCrisisCount, prGroups: prPending, support: openTickets }
    return extraSections.reduce((sum, item) => sum + (Number(map[item.id]) || 0), 0)
  }, [extraSections, tiktokPending, nikaCrisisCount, prPending, openTickets])

  const handleNikaPulse = useCallback((pulse) => {
    const n = Number(pulse?.openCritical || 0) + Number(pulse?.starvingCount || 0)
    setNikaCrisisCount(pulse?.crisis ? Math.max(1, n) : 0)
  }, [])
  useEffect(() => {
    const hasSupport = navSections.some((s) => s.id === 'support')
    const hasTiktok = navSections.some((s) => s.id === 'tiktok')
    const hasPr = navSections.some((s) => s.id === 'prGroups')
    if (!hasSupport && !hasTiktok && !hasPr) return
    let cancelled = false
    const load = () => {
      if (document.visibilityState !== 'visible') return
      if (hasSupport) {
        fetchSupportStats()
          .then((d) => { if (!cancelled) setOpenTickets(d.openTickets || 0) })
          .catch(() => {})
      }
      if (hasTiktok) {
        fetchTiktokCounts()
          .then((d) => { if (!cancelled) setTiktokPending(d.pendingTotal || 0) })
          .catch(() => {})
      }
      if (hasPr) {
        fetchPrOverview()
          .then((d) => { if (!cancelled) setPrPending(d.pending || 0) })
          .catch(() => {})
      }
    }
    load()
    const id = setInterval(load, 20_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [navSections])

  const handleLogout = useCallback(() => {
    logoutAdmin()
    onLogout?.()
  }, [onLogout])

  const handleSessionExpired = useCallback(() => {
    logoutAdmin()
    onLogout?.()
  }, [onLogout])

  // Register a global 401 handler so any request in any section auto-triggers logout
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      logoutAdmin()
      onLogout?.()
    })
    return () => registerUnauthorizedHandler(null)
  }, [onLogout])

  const handleNavigate = useCallback((id, opts = null) => {
    let next = id
    // «Админ панель» и старые «Права» живут внутри «Стафф».
    if (next === 'rights' || (next === 'panelAccess' && opts?.tab === 'rights')) {
      next = 'staff'
      setStaffEntry({ office: 'group', slice: 'posts' })
    } else if (next === 'panelAccess') {
      next = 'staff'
      setStaffEntry({ office: 'staff', slice: 'access' })
    } else if (next !== 'staff') {
      setStaffEntry(null)
    }
    if (next === 'content' && opts?.tab) {
      setContentInitialTab(opts.tab)
    } else if (next !== 'content') {
      setContentInitialTab(null)
    }
    if (next !== section) setFlashKey((k) => k + 1)
    setSection(next)
    setMobileNavOpen(false)
    if (next !== 'more') setRecentSections(pushRecentSection(next))
  }, [section])

  const currentSection = PANEL_SECTIONS.find((s) => s.id === section)

  const isDashboard = section === 'dashboard'
  const isUsers = section === 'users'
  const isAccounts = section === 'accounts'
  const isEconomy = section === 'economy'
  const isMarket = section === 'market'
  const isFarm = section === 'farm'
  const isContent = section === 'content'
  const isGiveaways = section === 'giveaways'
  const isTiktok = section === 'tiktok'
  const isBotQuests = section === 'botQuests'
  const isGroupBalanceLevel = section === 'groupBalanceLevel'
  const isGroupsStudio = section === 'groupsStudio'
  const isNika = section === 'nika'
  const isPrGroups = section === 'prGroups'
  const isGames = section === 'games'
  const isAchievements = section === 'achievements'
  const isBroadcast = section === 'broadcast'
  const isLogs = section === 'logs'
  const isAnalytics = section === 'analytics'
  const isSettings = section === 'settings'
  const isEvents = section === 'events'
  const isSecurity = section === 'security'
  const isStaff = section === 'staff'
  const isSupport = section === 'support'
  const isModeration = section === 'moderation'
  const isWork = section === 'work'
  const isChronicle  = section === 'chronicle'
  const isGroupGuard = section === 'groupGuard'
  const isSoftRestart = section === 'softRestart'

  if (preview?.kind === 'group') {
    return (
      <>
        <PanelBackgroundMusic volume={musicVolume} />
        <GroupShell
          portrait={preview.portrait}
          preview
          onLeave={exitPreview}
          banner={(
            <PanelPreviewBar
              title={previewTitle(preview)}
              detail="Тестовый режим: страницы, группы и наказания — как у настоящего кабинета. Ничего не сохраняется."
              onExit={exitPreview}
            />
          )}
        />
      </>
    )
  }

  return (
    <>
    <PanelBackgroundMusic volume={musicVolume} />
    <MetricSheetProvider>
    <div className={`panel-shell panel-shell-${viewport}`} data-viewport={viewport}>
      <AccentAura />
      {coach && (
        <FirstRun
          key={coachRun}
          storageKey="epsilon.onboard.staff.v4"
          steps={staffSteps(phone)}
          layoutKey={mobileNavOpen ? 1 : 0}
          onStep={onCoachStep}
          onDone={() => setCoach(false)}
        />
      )}
      {!coach && lesson && showWork && (
        <FirstRun
          key={`work-${coachRun}`}
          storageKey={workLessonKey}
          steps={workLessonSteps(isProjectCreator && !preview ? 'creator' : 'staff')}
          onStep={onCoachStep}
          onDone={() => setLesson(false)}
        />
      )}
      {/* Зарезервированная полоса под ✕ / меню Telegram + Dynamic Island */}
      <div className="panel-tg-chrome" aria-hidden="true" />
      {staffPreview && (
        <PanelPreviewBar
          title={previewTitle(staffPreview)}
          detail="Тестовый режим: меню, вкладки и права — как у настоящей панели. Ничего не сохраняется."
          onExit={exitPreview}
        />
      )}

      {godMode && role === 'owner' && !preview && (
        <CommandCenterSection onExit={() => setGodMode(false)} />
      )}
      {needsRules && !preview && <RulesGateModal onAccepted={() => setNeedsRules(false)} />}
      {flashKey > 0 && <div key={flashKey} className="section-flash" aria-hidden="true" />}
      <ToastHost />

      {/* Mobile: dimmer under fullscreen nav drawer */}
      {!phone && (
        <PanelDrawerOverlay open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} ms={700} />
      )}
      {!phone && (
        <PanelSidebar
          sections={navSections}
          activeSection={section}
          onNavigate={handleNavigate}
          onLogout={preview ? undefined : handleLogout}
          onChangeDoor={preview ? undefined : onChangeDoor}
          onExitPreview={preview ? exitPreview : undefined}
          onSessionExpired={handleSessionExpired}
          mobileOpen={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
          role={viewRole}
          lightMode={lightMode}
          onTogglePerf={() => setLightMode(!lightMode)}
          musicVolume={musicVolume}
          onMusicVolumeChange={setMusicVolume}
          onToggleMusic={toggleMusicMute}
          onEnterGodMode={() => setGodMode(true)}
          badges={{ support: openTickets, tiktok: tiktokPending, nika: nikaCrisisCount, prGroups: prPending }}
          accent={accent}
          onAccentChange={handleAccentChange}
          onReplayCoach={replayCoach}
          recentSectionIds={recentSections}
        />
      )}

      {showCreator && (
        <NikaCrisisStrip
          enabled={showCreator}
          onOpen={() => handleNavigate('nika')}
          onPulse={handleNikaPulse}
        />
      )}

      <main ref={mainRef} className="panel-shell-main">
        {phone && !isMore && (
          <div className="panel-appearance">
            <AccentPalette value={accent} onChange={handleAccentChange} />
          </div>
        )}
        <div
          className={`panel-layout${
            isDashboard || isUsers
              ? ' panel-layout-users'
              : isAccounts
                  ? ' panel-layout-accounts'
                  : isEconomy
                  ? ' panel-layout-economy'
                  : isMarket
                    ? ' panel-layout-market'
                    : isFarm
                      ? ' panel-layout-farm'
                      : isContent
                        ? ' panel-layout-content'
                        : isGiveaways
                        ? ' panel-layout-broadcast'
                        : isTiktok
                        ? ' panel-layout-broadcast'
                        : isBotQuests
                          ? ' panel-layout-broadcast'
                        : isGroupBalanceLevel || isGroupsStudio || isNika || isPrGroups || isGames
                          ? ' panel-layout-broadcast'
                        : isBroadcast
                        ? ' panel-layout-broadcast'
                        : isLogs
                          ? ' panel-layout-logs'
                          : isAnalytics
                            ? ' panel-layout-analytics'
                            : isSettings
                              ? ' panel-layout-settings'
                              : isEvents
                                ? ' panel-layout-events'
                                : isSecurity
                                  ? ' panel-layout-security'
                                  : isStaff
                                    ? ' panel-layout-staff'
                                    : isSupport
                                      ? ' panel-layout-support'
                                      : isChronicle
                                        ? ' panel-layout-chronicle'
                                        : isSoftRestart || isGroupsStudio || isNika || isGames
                                          ? ' panel-layout-security'
                                          : ' panel-layout-page'
          }`}
        >
          <EliteTopbar
            sections={navSections}
            activeSection={section}
            onNavigate={handleNavigate}
            openTickets={openTickets}
            onOpenNotifications={() => handleNavigate('support')}
            compact
            welcome={!phone && isDashboard}
            hideSearch={phone && isMore}
          />

          {phone && (
            <header className="craft-page-head">
              <h1>{isMore ? 'Ещё' : (navSections.find((item) => item.id === section)?.labelRu || 'Панель')}</h1>
            </header>
          )}

          {isMore && (
            <ExtrasHub
              sections={extraSections}
              badges={{ support: openTickets, tiktok: tiktokPending, nika: nikaCrisisCount, prGroups: prPending }}
              onOpen={handleNavigate}
              tools={phone ? (
                <PanelPocketTools
                  accent={accent}
                  onAccentChange={handleAccentChange}
                  lightMode={lightMode}
                  onTogglePerf={() => setLightMode(!lightMode)}
                  musicVolume={musicVolume}
                  onMusicVolumeChange={setMusicVolume}
                  onToggleMusic={toggleMusicMute}
                  onChangeDoor={preview ? undefined : onChangeDoor}
                  onExitPreview={preview ? exitPreview : undefined}
                  onLogout={preview ? undefined : handleLogout}
                  onSessionExpired={handleSessionExpired}
                  onReplayCoach={replayCoach}
                />
              ) : null}
            />
          )}

          {isDashboard && <DashboardSection />}
          {isUsers && (
            <UsersSection
              initialUserId={usersInitialId}
              onInitialUserConsumed={() => setUsersInitialId(null)}
              permissions={viewPermissions}
              role={viewRole}
              myUserId={viewUserId}
              isProjectCreator={showCreator}
              canBanfull={viewBanfull}
              canOpenGroups={navSections.some((s) => s.id === 'groupsStudio')}
              onOpenGroup={(chatId) => {
                setGroupsInitialId(chatId)
                setSection('groupsStudio')
              }}
            />
          )}
          {isAccounts && (
            <AccountsSection
              onOpenInUsers={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isEconomy && (
            <EconomySection
              onNavigate={(id) => handleNavigate(id, id === 'content' ? { tab: 'items' } : null)}
            />
          )}
          {isMarket && <MarketSection />}
          {isFarm && (
            <FarmSection
              isProjectCreator={showCreator}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isContent && (
            <ContentSection
              role={viewRole}
              panelTabs={tabsForView}
              initialTab={contentInitialTab}
              onInitialTabConsumed={() => setContentInitialTab(null)}
            />
          )}
          {isGiveaways && <GiveawaysSection />}
          {isTiktok && (
            <TikTokSection
              panelTabs={tabsForView}
              role={viewRole}
              isProjectCreator={showCreator}
            />
          )}
          {isBotQuests && viewRole === 'owner' && <BotQuestsSection />}
          {isGroupBalanceLevel && viewRole === 'owner' && <GroupBalanceLevelSection />}
          {isGroupsStudio && showCreator && (
            <GroupsStudioSection
              initialChatId={groupsInitialId}
              onInitialChatConsumed={() => setGroupsInitialId(null)}
              canBanfull={viewBanfull}
              permissions={viewPermissions}
              role={viewRole}
              isProjectCreator={showCreator}
              staffPerms={viewStaffPerms}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isNika && showCreator && <NikaSection />}
          {isPrGroups && showCreator && <PrGroupsSection />}
          {isGames && showCreator && <GamesSection />}
          {isAchievements && (
            <AchievementsSection
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isBroadcast && <BroadcastSection panelTabs={tabsForView} />}
          {isLogs && (
            <LogsSection
              panelTabs={tabsForView}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isAnalytics && <AnalyticsSection panelTabs={tabsForView} />}
          {isSettings && <SystemSection panelTabs={tabsForView} />}
          {isEvents && <EventsSection panelTabs={tabsForView} />}
          {isSecurity && <SecuritySection panelTabs={tabsForView} />}
          {isStaff && (
            <StaffSection
              role={viewRole}
              permissions={viewPermissions}
              myUserId={viewUserId}
              panelTabs={tabsForView}
              isProjectCreator={showCreator}
              entry={staffEntry}
              onOpenPreview={openPreview}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isSupport && <SupportSection />}
          {isWork && showWork && (
            <section className="grp-page nika-page realm-main work-page">
              <header className="nika-head">
                <div className="nika-head-copy">
                  <h1>Работа</h1>
                </div>
              </header>
              {isProjectCreator && !preview
                ? <CreatorDeck onCount={setWorkCount} />
                : <StaffDesk onCount={setWorkCount} />}
              <WorkLessonButton onClick={openWorkLesson} />
            </section>
          )}
          {isModeration && (
            <ModerationSection
              role={viewRole}
              permissions={viewPermissions}
              panelTabs={tabsForView}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isChronicle && <ChronicleSection />}
          {isGroupGuard && showCreator && <GroupGuardDesk />}
          {isSoftRestart && showCreator && <SoftRestartSection />}
          {!isMore && !isDashboard && !isUsers && !isAccounts && !isEconomy && !isMarket && !isFarm && !isContent && !isGiveaways && !isTiktok && !isBotQuests && !isGroupBalanceLevel && !isGroupsStudio && !isNika && !isPrGroups && !isGames && !isAchievements && !isBroadcast && !isLogs && !isAnalytics && !isSettings && !isEvents && !isSecurity && !isStaff && !isSupport && !isModeration && !isWork && !isChronicle && !isGroupGuard && !isSoftRestart && (
            <SectionPlaceholder sectionId={section} />
          )}
        </div>
      </main>
      <PhoneDock
        sections={dockSections}
        activeSection={dockActiveId(section, primaryIds)}
        onNavigate={handleNavigate}
        badges={{
          support: openTickets,
          work: workCount,
          tiktok: tiktokPending,
          nika: nikaCrisisCount,
          prGroups: prPending,
          more: moreBadge,
        }}
        menuOpen={!phone && mobileNavOpen}
        onOpenMenu={phone ? undefined : () => setMobileNavOpen((open) => !open)}
      />
    </div>
    </MetricSheetProvider>
    </>
  )
}
