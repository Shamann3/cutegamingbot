import { useEffect, useMemo, useRef, useState } from 'react'
import { getAdminInitials, getAdminProfile } from '../lib/adminProfile'
import { groupSections, SECTION_HINTS } from '../constants/panelNav'
import { NAV_ICONS } from './NavIcons'
import SessionTimer from './SessionTimer'
import EpsilonLogo from './EpsilonLogo'
import AccentPalette from './AccentPalette'
import { useIsPhone } from '../lib/useIsDesktop'
import { CopyableUsername } from './Copyable'
import { telegramDissolve } from '../lib/telegramDissolve'

const DISSOLVE_MS = 700

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

function SettingsControls({
  accent,
  onAccentChange,
  onSessionExpired,
  musicVolume,
  onToggleMusic,
  onMusicVolumeChange,
  lightMode,
  onTogglePerf,
}) {
  return (
    <>
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
        title={lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
      >
        <span aria-hidden="true">{lightMode ? '◈' : '⬡'}</span>
        {lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
      </button>
    </>
  )
}

export default function PanelSidebar({
  sections,
  activeSection,
  onNavigate,
  onLogout,
  onChangeDoor,
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
  brandName = 'Панель сотрудника',
  brandTag = 'Весь проект',
}) {
  const isPhone = useIsPhone()
  const { displayName, username, photoUrl } = getAdminProfile()
  const initials = getAdminInitials(displayName)
  const [navQuery, setNavQuery] = useState('')
  const asideRef = useRef(null)
  const [visuallyOpen, setVisuallyOpen] = useState(mobileOpen)
  const [dissolving, setDissolving] = useState(false)
  const dissolvingRef = useRef(false)

  // Закрытие: испарение на частицы (как удаление сообщения в Telegram), ≤0.7с
  useEffect(() => {
    const el = asideRef.current
    if (mobileOpen) {
      dissolvingRef.current = false
      setDissolving(false)
      setVisuallyOpen(true)
      if (el) {
        el.style.visibility = ''
        el.style.pointerEvents = ''
        el.style.opacity = ''
      }
      return undefined
    }
    if (!visuallyOpen) return undefined
    if (dissolvingRef.current) return undefined
    dissolvingRef.current = true
    setDissolving(true)
    let cancelled = false
    ;(async () => {
      await telegramDissolve(el, { duration: DISSOLVE_MS })
      if (cancelled) return
      setVisuallyOpen(false)
      setDissolving(false)
      dissolvingRef.current = false
    })()
    return () => {
      cancelled = true
    }
  }, [mobileOpen, visuallyOpen])

  const goTo = (id) => {
    onNavigate(id)
  }

  const navGroups = useMemo(() => {
    const groups = groupSections(sections)
    const q = navQuery.trim().toLowerCase().replace(/ё/g, 'е')
    if (!q) return groups
    return groups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => {
          const ru = (item.labelRu || '').toLowerCase().replace(/ё/g, 'е')
          const en = (item.label || '').toLowerCase()
          const id = (item.id || '').toLowerCase()
          return ru.includes(q) || en.includes(q) || id.includes(q)
        }),
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
    if (!isPhone) return undefined
    if (!mobileOpen) {
      setNavQuery('')
    }
    return undefined
  }, [mobileOpen, isPhone])

  // Клик вне панели (сотрудники и админы) — закрыть. Overlay тоже закрывает;
  // этот слушатель ловит случаи, когда клик прошёл мимо dimmer.
  useEffect(() => {
    if (!mobileOpen || typeof onClose !== 'function') return undefined
    const onPointer = (event) => {
      if (dissolvingRef.current) return
      const root = event.target?.closest?.('.panel-shelf-sidebar, .panel-dissolve-canvas')
      const dock = event.target?.closest?.('.phone-dock, .phone-edge, .elite-menu-btn')
      const palette = event.target?.closest?.('.accent-picker-panel, .accent-picker-root, .accent-wheel-wrap')
      if (root || dock || palette) return
      onClose()
    }
    document.addEventListener('pointerdown', onPointer, true)
    return () => document.removeEventListener('pointerdown', onPointer, true)
  }, [mobileOpen, onClose])

  const settingsProps = {
    accent,
    onAccentChange,
    onSessionExpired,
    musicVolume,
    onToggleMusic,
    onMusicVolumeChange,
    lightMode,
    onTogglePerf,
  }

  return (
    <aside
      ref={asideRef}
      className={`panel-shelf panel-shelf-sidebar${visuallyOpen ? ' panel-sidebar-mobile-open' : ''}${dissolving ? ' is-dissolving' : ''}`}
    >
      {/* Mobile drawer chrome — на desktop скрыт CSS */}
      <div className="panel-sidebar-grab">
        <div className="panel-sidebar-drawer-head">
          <div>
            <h2 className="panel-sidebar-drawer-title">{isPhone ? 'Меню' : 'Страницы'}</h2>
            <p className="panel-sidebar-swipe-hint">
              {isPhone
                ? 'Все разделы здесь. Настройки — внизу этого меню.'
                : 'Нажмите название раздела.'}
            </p>
          </div>
          <button
            type="button"
            className="panel-sidebar-close"
            aria-label="Закрыть меню"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <label className="panel-sidebar-search" data-coach="search">
          <span className="panel-sidebar-search-icon" aria-hidden="true">⌕</span>
          <input
            className="panel-sidebar-search-field"
            type="text"
            inputMode="search"
            value={navQuery}
            onChange={(e) => setNavQuery(e.target.value)}
            placeholder="Найти раздел…"
            aria-label="Поиск раздела в меню"
            enterKeyHint="search"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
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
          <p className="panel-brand-name">{brandName}</p>
          <p className="panel-brand-tag">{brandTag}</p>
        </div>
      </div>

      <nav className="panel-sidebar-nav" data-coach="nav" aria-label="Навигация панели">
        {!isPhone && !navQuery.trim() && recentItems.length > 0 && (
          <div className="panel-nav-group panel-nav-recent">
            <span className="panel-nav-group-label" aria-hidden="true">
              Недавно открывали
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
                    onClick={() => goTo(item.id)}
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
                  onClick={() => goTo(item.id)}
                >
                  {NavIcon && (
                    <span className="panel-nav-icon">
                      <NavIcon />
                    </span>
                  )}
                  <span className="panel-nav-text">
                    <span className="panel-nav-label">{item.labelRu}</span>
                    {SECTION_HINTS[item.id] && (
                      <span className="panel-nav-sublabel">{SECTION_HINTS[item.id]}</span>
                    )}
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
        {isPhone ? (
          <>
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
                  {role === 'owner' ? 'Владелец' : username ? <CopyableUsername value={username} /> : 'Cute Epsilon'}
                </p>
              </div>
            </div>

            <div className="panel-sidebar-settings panel-sidebar-settings-pin">
              <p className="panel-sidebar-settings-label">Настройки</p>
              <div className="panel-sidebar-settings-body">
                <AccentPalette value={accent} onChange={onAccentChange} />
                <SettingsControls {...settingsProps} />
              </div>
            </div>
          </>
        ) : (
          <>
            {/* ПК: Подсветка выше профиля */}
            <div className="panel-sidebar-settings panel-sidebar-settings-desktop">
              <div className="panel-sidebar-settings-body">
                <AccentPalette value={accent} onChange={onAccentChange} />
              </div>
            </div>

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
                  {role === 'owner' ? 'Владелец' : username ? <CopyableUsername value={username} /> : 'Cute Epsilon'}
                </p>
              </div>
            </div>

            <div className="panel-sidebar-settings panel-sidebar-settings-desktop">
              <div className="panel-sidebar-settings-body">
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
                  title={lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
                >
                  <span aria-hidden="true">{lightMode ? '◈' : '⬡'}</span>
                  {lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
                </button>
              </div>
            </div>
          </>
        )}

        {onChangeDoor && (
          <button type="button" className="panel-logout-btn" data-coach="doors" onClick={onChangeDoor}>
            Сменить панель
            <span className="panel-logout-hint">выбор панели, без выхода из аккаунта</span>
          </button>
        )}
        {onLogout && (
          <button type="button" className="panel-logout-btn" onClick={onLogout}>
            Выйти
          </button>
        )}
      </div>
    </aside>
  )
}
