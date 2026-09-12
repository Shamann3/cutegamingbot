import { useEffect, useMemo, useState } from 'react'
import { getAdminInitials, getAdminProfile } from '../lib/adminProfile'
import { groupSections } from '../constants/panelNav'
import { NAV_ICONS } from './NavIcons'
import SessionTimer from './SessionTimer'
import EpsilonLogo from './EpsilonLogo'
import AccentPalette from './AccentPalette'

function SpeakerIcon({ muted }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="1em"
      height="1em"
      aria-hidden="true"
    >
      <path d="M4 9v6h4l5 4V5L8 9H4z" />
      {muted ? (
        <>
          <line x1="16" y1="9" x2="21" y2="14" />
          <line x1="21" y1="9" x2="16" y2="14" />
        </>
      ) : (
        <>
          <path d="M16.5 8.5a5 5 0 0 1 0 7" />
          <path d="M19 6a8.5 8.5 0 0 1 0 12" />
        </>
      )}
    </svg>
  )
}

export default function PanelSidebar({
  sections,
  activeSection,
  onNavigate,
  onLogout,
  onSessionExpired,
  mobileOpen = false,
  onClose,
  role = null,
  lightMode = false,
  onTogglePerf,
  musicVolume = 0,
  onMusicVolumeChange,
  onToggleMusic,
  badges = {},
  accent = null,
  onAccentChange,
  recentSectionIds = [],
}) {
  const { displayName, username, photoUrl } = getAdminProfile()
  const initials = getAdminInitials(displayName)
  const [navQuery, setNavQuery] = useState('')

  const navGroups = useMemo(() => {
    const groups = groupSections(sections)
    const q = navQuery.trim().toLowerCase()
    if (!q) return groups
    return groups
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (item) =>
            item.labelRu.toLowerCase().includes(q) ||
            item.label.toLowerCase().includes(q),
        ),
      }))
      .filter((group) => group.items.length > 0)
  }, [sections, navQuery])

  const recentItems = useMemo(() => {
    const byId = new Map(sections.map((s) => [s.id, s]))
    return (recentSectionIds || [])
      .map((id) => byId.get(id))
      .filter(Boolean)
      .slice(0, 5)
  }, [sections, recentSectionIds])

  useEffect(() => {
    if (!mobileOpen) setNavQuery('')
  }, [mobileOpen])

  return (
    <aside
      className={`panel-shelf panel-shelf-sidebar${mobileOpen ? ' panel-sidebar-mobile-open' : ''}`}
    >
      {/* Mobile drawer chrome — на desktop скрыт */}
      <div className="panel-sidebar-grab">
        <div className="panel-sidebar-drawer-head">
          <h2 className="panel-sidebar-drawer-title">Меню</h2>
          <button
            type="button"
            className="panel-sidebar-close"
            aria-label="Закрыть меню"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <label className="panel-sidebar-search">
          <span className="panel-sidebar-search-icon" aria-hidden="true">⌕</span>
          <input
            type="search"
            value={navQuery}
            onChange={(e) => setNavQuery(e.target.value)}
            placeholder="Найти раздел…"
            aria-label="Поиск раздела в меню"
            enterKeyHint="search"
            autoComplete="off"
          />
        </label>
      </div>

      {/* Бренд — только desktop */}
      <div className="panel-brand" aria-label="Epsilon">
        <div className="panel-brand-crest" aria-hidden="true">
          <span className="panel-brand-halo" />
          <span className="panel-brand-ring" />
          <div className="panel-brand-mark">
            <EpsilonLogo size="sm" decorative />
          </div>
        </div>
        <div className="panel-brand-meta">
          <p className="panel-brand-name">Epsilon</p>
          <p className="panel-brand-tag">Управление</p>
        </div>
      </div>

      <nav className="panel-sidebar-nav" aria-label="Навигация панели">
        {!navQuery.trim() && recentItems.length > 0 && (
          <div className="panel-nav-group panel-nav-recent">
            <span className="panel-nav-group-label" aria-hidden="true">
              Недавние
            </span>
            <div className="panel-nav-recent-row">
              {recentItems.map((item) => {
                const Icon = NAV_ICONS[item.id]
                const active = item.id === activeSection
                return (
                  <button
                    key={item.id}
                    type="button"
                    className="panel-nav-recent-chip"
                    aria-current={active ? 'page' : undefined}
                    onClick={() => onNavigate(item.id)}
                  >
                    {Icon && <Icon />}
                    {item.labelRu}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {navGroups.map((group) => (
          <div className="panel-nav-group" key={group.id}>
            {group.label && (
              <span className="panel-nav-group-label" aria-hidden="true">
                {group.label}
              </span>
            )}
            {group.items.map((item) => {
              const active = item.id === activeSection
              const NavIcon = NAV_ICONS[item.id]
              const count = badges[item.id]
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`panel-nav-item${active ? ' panel-nav-item-active' : ''}`}
                  data-section={item.id}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => onNavigate(item.id)}
                >
                  {NavIcon && (
                    <span className="panel-nav-icon">
                      <NavIcon />
                    </span>
                  )}
                  <span className="panel-nav-text">
                    <span className="panel-nav-label">{item.labelRu}</span>
                    <span className="panel-nav-sublabel">{item.label}</span>
                  </span>
                  {count > 0 && (
                    <span className="panel-nav-badge" aria-label={`${count} новых`}>
                      {count > 99 ? '99+' : count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
        {navQuery.trim() && navGroups.length === 0 && (
          <p className="panel-sidebar-search-empty">Ничего не найдено</p>
        )}
      </nav>

      <div className="panel-sidebar-footer">
        <div className="panel-sidebar-account">
          <div className="panel-profile-avatar" aria-hidden="true">
            {photoUrl ? (
              <img className="panel-profile-photo" src={photoUrl} alt="" />
            ) : (
              <span className="panel-profile-initials">{initials}</span>
            )}
          </div>
          <div className="panel-profile-meta">
            <p className="panel-profile-name">{displayName}</p>
            <p className="panel-profile-kicker">
              {role === 'owner' ? 'Владелец' : username ? `@${username}` : 'Cute Epsilon'}
            </p>
          </div>
        </div>

        {/*
          Desktop: тело настроек всегда видно (summary скрыт CSS).
          Mobile: свёрнутый блок «Настройки».
        */}
        <details className="panel-sidebar-settings">
          <summary className="panel-sidebar-settings-sum">
            <span>Настройки</span>
            <span className="panel-sidebar-settings-chevron" aria-hidden="true">▾</span>
          </summary>
          <div className="panel-sidebar-settings-body">
            <AccentPalette value={accent} onChange={onAccentChange} />

            <SessionTimer compact onExpired={onSessionExpired} />

            <div className="panel-music-card">
              <div className="panel-music-head">
                <button
                  type="button"
                  className="panel-music-icon-btn"
                  onClick={onToggleMusic}
                  title={musicVolume > 0 ? 'Выключить музыку' : 'Включить музыку'}
                  aria-pressed={musicVolume > 0}
                >
                  <SpeakerIcon muted={musicVolume <= 0} />
                </button>
                <span className="panel-music-label">Музыка</span>
                <span className="panel-music-pct">{Math.round(musicVolume * 100)}%</span>
              </div>
              <input
                type="range"
                className="panel-music-slider"
                min={0}
                max={100}
                step={1}
                value={Math.round(musicVolume * 100)}
                onChange={(e) => onMusicVolumeChange(Number(e.target.value) / 100)}
                style={{ '--vol-pct': `${Math.round(musicVolume * 100)}%` }}
                aria-label="Громкость музыки"
              />
            </div>

            <button
              type="button"
              className={`panel-perf-btn${lightMode ? ' panel-perf-btn-active' : ''}`}
              onClick={onTogglePerf}
              title={lightMode ? 'Чёрно-белый лёгкий режим' : 'Цветной HD — подсветка из палитры'}
            >
              <span aria-hidden="true">{lightMode ? '◈' : '⬡'}</span>
              {lightMode ? 'Ч/Б · лёгкий' : 'HD · цвет'}
            </button>
          </div>
        </details>

        <button type="button" className="panel-logout-btn" onClick={onLogout}>
          Выйти
        </button>
      </div>
    </aside>
  )
}
