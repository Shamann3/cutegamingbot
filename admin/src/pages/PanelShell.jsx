import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PANEL_SECTIONS, visibleSections, splitDockSections, dockActiveId } from '../constants/panelNav'
import PanelSidebar from '../components/PanelSidebar'
import EliteTopbar from '../components/EliteTopbar'
import ToastHost from '../components/ToastHost'
import { fetchAdminMe, fetchPrOverview, fetchSupportStats, fetchTiktokCounts, logoutAdmin, registerUnauthorizedHandler } from '../lib/adminClient'
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
import PanelAccessSection from './sections/PanelAccessSection'
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
import FirstRun, { staffSteps, coachClosed } from '../components/FirstRun'
import PhoneDock from '../components/PhoneDock'
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
  const [panelAccessInitialTab, setPanelAccessInitialTab] = useState(null)
  const [recentSections, setRecentSections] = useState(() => loadRecentSections())
  const [coach, setCoach] = useState(() => !coachClosed('epsilon.onboard.staff.v4'))
  const onCoachStep = useCallback((step) => {
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

  const navSections = useMemo(
    () => visibleSections(permissions, panelSections, role, {
      myUserId,
      projectCreatorId,
      isProjectCreator,
    }),
    [permissions, panelSections, role, myUserId, projectCreatorId, isProjectCreator],
  )

  const { dock: dockSections, extras: extraSections, primaryIds } = useMemo(
    () => splitDockSections(navSections),
    [navSections],
  )

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
    // Старый раздел «Права» влит в «Админ панель»
    if (next === 'rights') {
      next = 'panelAccess'
      setPanelAccessInitialTab(opts?.tab || 'punish')
    } else if (next === 'panelAccess' && opts?.tab) {
      setPanelAccessInitialTab(opts.tab)
    } else if (next !== 'panelAccess') {
      setPanelAccessInitialTab(null)
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
  const isChronicle  = section === 'chronicle'
  const isPanelAccess = section === 'panelAccess' || section === 'rights'
  const isGroupGuard = section === 'groupGuard'
  const isSoftRestart = section === 'softRestart'

  return (
    <MetricSheetProvider>
    <div className={`panel-shell panel-shell-${viewport}`} data-viewport={viewport}>
      <AccentAura />
      {coach && (
        <FirstRun
          storageKey="epsilon.onboard.staff.v4"
          steps={staffSteps(phone)}
          layoutKey={mobileNavOpen ? 1 : 0}
          onStep={onCoachStep}
          onDone={() => setCoach(false)}
        />
      )}
      {/* Зарезервированная полоса под ✕ / меню Telegram + Dynamic Island */}
      <div className="panel-tg-chrome" aria-hidden="true" />

      {godMode && role === 'owner' && (
        <CommandCenterSection onExit={() => setGodMode(false)} />
      )}
      {needsRules && <RulesGateModal onAccepted={() => setNeedsRules(false)} />}
      {flashKey > 0 && <div key={flashKey} className="section-flash" aria-hidden="true" />}
      <ToastHost />
      <PanelBackgroundMusic volume={musicVolume} />

      {/* Mobile: dimmer under fullscreen nav drawer */}
      {!phone && (
        <PanelDrawerOverlay open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} ms={700} />
      )}
      {!phone && (
        <PanelSidebar
          sections={navSections}
          activeSection={section}
          onNavigate={handleNavigate}
          onLogout={handleLogout}
          onChangeDoor={onChangeDoor}
          onSessionExpired={handleSessionExpired}
          mobileOpen={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
          role={role}
          lightMode={lightMode}
          onTogglePerf={() => setLightMode(!lightMode)}
          musicVolume={musicVolume}
          onMusicVolumeChange={setMusicVolume}
          onToggleMusic={toggleMusicMute}
          onEnterGodMode={() => setGodMode(true)}
          badges={{ support: openTickets, tiktok: tiktokPending, nika: nikaCrisisCount, prGroups: prPending }}
          accent={accent}
          onAccentChange={handleAccentChange}
          recentSectionIds={recentSections}
        />
      )}

      {isProjectCreator && (
        <NikaCrisisStrip
          enabled={isProjectCreator}
          onOpen={() => handleNavigate('nika')}
          onPulse={handleNikaPulse}
        />
      )}

      <main ref={mainRef} className="panel-shell-main">
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
                                        : isPanelAccess || isSoftRestart || isGroupsStudio || isNika || isGames
                                          ? ' panel-layout-security'
                                          : ' panel-layout-page'
          }`}
        >
          {!phone && (
            <EliteTopbar
              sections={navSections}
              activeSection={section}
              onNavigate={handleNavigate}
              openTickets={openTickets}
              onOpenNotifications={() => handleNavigate('support')}
              compact
              welcome={isDashboard}
            />
          )}

          {phone && !isMore && (
            <header className="craft-page-head">
              <h1>{navSections.find((item) => item.id === section)?.labelRu || 'Панель'}</h1>
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
                  onChangeDoor={onChangeDoor}
                  onLogout={handleLogout}
                  onSessionExpired={handleSessionExpired}
                />
              ) : null}
            />
          )}

          {isDashboard && <DashboardSection />}
          {isUsers && (
            <UsersSection
              initialUserId={usersInitialId}
              onInitialUserConsumed={() => setUsersInitialId(null)}
              permissions={permissions}
              role={role}
              myUserId={myUserId}
              isProjectCreator={isProjectCreator}
              canBanfull={canBanfull}
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
              isProjectCreator={isProjectCreator}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isContent && (
            <ContentSection
              role={role}
              panelTabs={panelTabs}
              initialTab={contentInitialTab}
              onInitialTabConsumed={() => setContentInitialTab(null)}
            />
          )}
          {isGiveaways && <GiveawaysSection />}
          {isTiktok && (
            <TikTokSection
              panelTabs={panelTabs}
              role={role}
              isProjectCreator={isProjectCreator}
            />
          )}
          {isBotQuests && role === 'owner' && <BotQuestsSection />}
          {isGroupBalanceLevel && role === 'owner' && <GroupBalanceLevelSection />}
          {isGroupsStudio && isProjectCreator && (
            <GroupsStudioSection
              initialChatId={groupsInitialId}
              onInitialChatConsumed={() => setGroupsInitialId(null)}
              canBanfull={canBanfull}
              permissions={permissions}
              role={role}
              isProjectCreator={isProjectCreator}
              staffPerms={staffPerms}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isNika && isProjectCreator && <NikaSection />}
          {isPrGroups && isProjectCreator && <PrGroupsSection />}
          {isGames && isProjectCreator && <GamesSection />}
          {isAchievements && (
            <AchievementsSection
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isBroadcast && <BroadcastSection panelTabs={panelTabs} />}
          {isLogs && (
            <LogsSection
              panelTabs={panelTabs}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isAnalytics && <AnalyticsSection panelTabs={panelTabs} />}
          {isSettings && <SystemSection panelTabs={panelTabs} />}
          {isEvents && <EventsSection panelTabs={panelTabs} />}
          {isSecurity && <SecuritySection panelTabs={panelTabs} />}
          {isStaff && <StaffSection role={role} permissions={permissions} myUserId={myUserId} panelTabs={panelTabs} isProjectCreator={isProjectCreator} />}
          {isSupport && <SupportSection />}
          {isModeration && (
            <ModerationSection
              role={role}
              permissions={permissions}
              panelTabs={panelTabs}
              onOpenUser={(userId) => {
                setUsersInitialId(userId)
                setSection('users')
              }}
            />
          )}
          {isChronicle && <ChronicleSection />}
          {isPanelAccess && (
            <PanelAccessSection
              isProjectCreator={isProjectCreator}
              initialTab={panelAccessInitialTab || (section === 'rights' ? 'punish' : null)}
            />
          )}
          {isGroupGuard && isProjectCreator && <GroupGuardDesk />}
          {isSoftRestart && isProjectCreator && <SoftRestartSection />}
          {!isMore && !isDashboard && !isUsers && !isAccounts && !isEconomy && !isMarket && !isFarm && !isContent && !isGiveaways && !isTiktok && !isBotQuests && !isGroupBalanceLevel && !isGroupsStudio && !isNika && !isPrGroups && !isGames && !isAchievements && !isBroadcast && !isLogs && !isAnalytics && !isSettings && !isEvents && !isSecurity && !isStaff && !isSupport && !isModeration && !isChronicle && !isPanelAccess && !isGroupGuard && !isSoftRestart && (
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
  )
}
