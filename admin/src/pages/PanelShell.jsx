import { useCallback, useEffect, useMemo, useState } from 'react'
import { PANEL_SECTIONS, visibleSections } from '../constants/panelNav'
import PanelSidebar from '../components/PanelSidebar'
import EliteTopbar from '../components/EliteTopbar'
import PanelBackdrop from '../components/PanelBackdrop'
import GoldBackdrop from '../components/GoldBackdrop'
import { NAV_ICONS } from '../components/NavIcons'
import ToastHost from '../components/ToastHost'
import { fetchAdminMe, fetchSupportStats, logoutAdmin, registerUnauthorizedHandler } from '../lib/adminClient'
import DashboardSection from './sections/DashboardSection'
import SectionPlaceholder from './sections/SectionPlaceholder'
import UsersSection from './sections/UsersSection'
import AccountsSection from './sections/AccountsSection'
import EconomySection from './sections/EconomySection'
import MarketSection from './sections/MarketSection'
import FarmSection from './sections/FarmSection'
import ContentSection from './sections/ContentSection'
import GiveawaysSection from './sections/GiveawaysSection'
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
import CursorGlow from '../components/CursorGlow'
import PanelBackgroundMusic from '../components/PanelBackgroundMusic'
import { usePerfMode } from '../lib/perfMode'
import { useMusicMode } from '../lib/musicMode'
import { useGlobalKeys } from '../lib/useGlobalKeys'

export default function PanelShell({ onLogout }) {
  const { lightMode, setLightMode } = usePerfMode()
  const { volume: musicVolume, setVolume: setMusicVolume, toggleMute: toggleMusicMute } = useMusicMode()

  // Глобальные горячие клавиши
  useGlobalKeys({
    onEscape: () => setMobileNavOpen(false),
  })
  const [section, setSection] = useState('dashboard')
  const [flashKey, setFlashKey] = useState(0)
  const [usersInitialId, setUsersInitialId] = useState(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [permissions, setPermissions] = useState([])
  const [panelSections, setPanelSections] = useState(null)
  const [role, setRole] = useState(null)
  const [myUserId, setMyUserId] = useState(null)
  const [needsRules, setNeedsRules] = useState(false)
  const [godMode, setGodMode] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchAdminMe()
      .then((me) => {
        if (cancelled) return
        setPermissions(me.permissions || [])
        setPanelSections(Array.isArray(me.panelSections) ? me.panelSections : null)
        setRole(me.role || null)
        setMyUserId(me.userId || null)
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
    () => visibleSections(permissions, panelSections),
    [permissions, panelSections],
  )

  // Если текущий раздел закрыли в матрице — уводим на первую доступную вкладку.
  useEffect(() => {
    if (!navSections.length) return
    if (!navSections.some((s) => s.id === section)) {
      setSection(navSections[0].id)
    }
  }, [navSections, section])

  // Счётчик открытых обращений — питает значок у пункта «Поддержка» и точку
  // на колокольчике. Опрашиваем только когда вкладка на экране, чтобы
  // фоновая панель не долбила API.
  const [openTickets, setOpenTickets] = useState(0)
  useEffect(() => {
    if (!navSections.some((s) => s.id === 'support')) return
    let cancelled = false
    const load = () => {
      if (document.visibilityState !== 'visible') return
      fetchSupportStats()
        .then((d) => { if (!cancelled) setOpenTickets(d.openTickets || 0) })
        .catch(() => {})
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

  const handleNavigate = useCallback((id) => {
    if (id !== section) setFlashKey((k) => k + 1)
    setSection(id)
    setMobileNavOpen(false)
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
  const isPanelAccess = section === 'panelAccess'

  return (
    <div className="panel-shell">
      {godMode && role === 'owner' && (
        <CommandCenterSection onExit={() => setGodMode(false)} />
      )}
      {needsRules && <RulesGateModal onAccepted={() => setNeedsRules(false)} />}
      {flashKey > 0 && <div key={flashKey} className="section-flash" aria-hidden="true" />}
      <ToastHost />
      <PanelBackgroundMusic volume={musicVolume} />
      <GoldBackdrop lightMode={lightMode} />
      <PanelBackdrop active />
      {!lightMode && <CursorGlow />}

      {/* Mobile: bottom navigation bar с быстрыми вкладками */}
      <footer className="panel-mobile-bottombar">
        {/* Быстрые вкладки — самые нужные разделы */}
        {[
          { id: 'dashboard', label: 'Главная' },
          { id: 'users',     label: 'Игроки' },
          { id: 'staff',     label: 'Стафф' },
          { id: 'support',   label: 'Помощь' },
          { id: 'moderation',label: 'Архив' },
        ].filter(tab => navSections.some(s => s.id === tab.id)).map(tab => {
          const TabIcon = NAV_ICONS[tab.id]
          return (
            <button
              key={tab.id}
              className={`panel-mobile-tab${section === tab.id ? ' panel-mobile-tab-active' : ''}`}
              onClick={() => handleNavigate(tab.id)}
            >
              <span className="panel-mobile-tab-icon">{TabIcon && <TabIcon />}</span>
              <span className="panel-mobile-tab-label">{tab.label}</span>
            </button>
          )
        })}
        {/* Кнопка «Ещё» открывает полное меню */}
        <button
          className={`panel-mobile-tab${mobileNavOpen ? ' panel-mobile-tab-active' : ''}`}
          aria-label="Все разделы"
          onClick={() => setMobileNavOpen((v) => !v)}
        >
          <span className="panel-mobile-tab-icon">
            <span className={`panel-hamburger-icon${mobileNavOpen ? ' panel-hamburger-icon-open' : ''}`} style={{ display: 'inline-block', width: 20, height: 14, position: 'relative' }} />
          </span>
          <span className="panel-mobile-tab-label">Ещё</span>
        </button>
      </footer>

      {/* Mobile: overlay backdrop */}
      {mobileNavOpen && (
        <div
          className="panel-mobile-overlay"
          aria-hidden="true"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <main className="panel-shell-main">
        <div
          className={`panel-layout${
            isDashboard
              ? ' panel-layout-dashboard'
              : isUsers
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
                                        : isPanelAccess
                                          ? ' panel-layout-panel-access'
                                          : ' panel-layout-page'
          }`}
        >
          <PanelSidebar
            sections={navSections}
            activeSection={section}
            onNavigate={handleNavigate}
            onLogout={handleLogout}
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
            badges={{ support: openTickets }}
          />

          <EliteTopbar
            sections={navSections}
            activeSection={section}
            onNavigate={handleNavigate}
            openTickets={openTickets}
            onOpenNotifications={() => handleNavigate('support')}
            compact={section !== 'dashboard'}
          />

          {isDashboard && <DashboardSection />}
          {isUsers && (
            <UsersSection
              initialUserId={usersInitialId}
              onInitialUserConsumed={() => setUsersInitialId(null)}
              permissions={permissions}
              role={role}
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
          {isEconomy && <EconomySection />}
          {isMarket && <MarketSection />}
          {isFarm && <FarmSection />}
          {isContent && <ContentSection role={role} />}
          {isGiveaways && <GiveawaysSection />}
          {isBroadcast && <BroadcastSection />}
          {isLogs && <LogsSection />}
          {isAnalytics && <AnalyticsSection />}
          {isSettings && <SystemSection />}
          {isEvents && <EventsSection />}
          {isSecurity && <SecuritySection />}
          {isStaff && <StaffSection role={role} permissions={permissions} myUserId={myUserId} />}
          {isSupport && <SupportSection />}
          {isModeration && <ModerationSection role={role} permissions={permissions} />}
          {isChronicle && <ChronicleSection />}
          {isPanelAccess && <PanelAccessSection />}
          {!isDashboard && !isUsers && !isAccounts && !isEconomy && !isMarket && !isFarm && !isContent && !isGiveaways && !isBroadcast && !isLogs && !isAnalytics && !isSettings && !isEvents && !isSecurity && !isStaff && !isSupport && !isModeration && !isChronicle && !isPanelAccess && (
            <SectionPlaceholder sectionId={section} />
          )}
        </div>
      </main>
    </div>
  )
}
