import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { getAdminInitials, getAdminProfile } from '../lib/adminProfile'
import { NAV_ICONS } from './NavIcons'
import SessionTimer from './SessionTimer'

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
}) {
  const { displayName, username, photoUrl } = getAdminProfile()
  const initials = getAdminInitials(displayName)

  const navRef = useRef(null)
  const sidebarRef = useRef(null)
  const grabRef = useRef(null)
  const [indicator, setIndicator] = useState({ top: 0, height: 0, visible: false })

  // Свайп-вниз для закрытия bottom-sheet на мобильных.
  //
  // ВАЖНО: обработчики висят ТОЛЬКО на «ручке» (grab-handle) сверху листа, а не на
  // всём сайдбаре. Раньше touch-обработчики покрывали все пункты навигации, и любое
  // микродвижение пальца во время тапа считалось началом drag → touchmove +
  // preventDefault отменяли click, и кнопки «не нажимались» на телефоне. Теперь тапы
  // по пунктам меню вообще не попадают в drag-логику — они срабатывают всегда.
  //
  // Слушатели нативные и non-passive, чтобы preventDefault реально гасил прокрутку
  // страницы во время перетаскивания. Трансформация ставится с приоритетом important,
  // иначе её перебивает правило `.panel-sidebar-mobile-open { transform: ... !important }`.
  useEffect(() => {
    const handle = grabRef.current
    const sheet = sidebarRef.current
    if (!handle || !sheet) return

    const THRESHOLD = 6 // px — порог, ниже которого жест считается тапом, а не drag
    let startY = null
    let active = false

    const setTransform = (px) => {
      if (px === null) sheet.style.removeProperty('transform')
      else sheet.style.setProperty('transform', `translateY(${px}px)`, 'important')
    }

    const onStart = (e) => {
      startY = e.touches[0].clientY
      active = false
    }

    const onMove = (e) => {
      if (startY === null) return
      const dy = e.touches[0].clientY - startY
      if (dy <= 0) {
        if (active) setTransform(0)
        return
      }
      // Пока палец не сдвинулся дальше порога — это ещё тап, не мешаем.
      if (!active && dy < THRESHOLD) return
      active = true
      e.preventDefault() // гасим прокрутку страницы во время drag
      const resistance = 1 - Math.min(dy / 600, 0.4) // «резинка»
      setTransform(dy * resistance)
    }

    const onEnd = (e) => {
      if (startY === null) return
      const dy = (e.changedTouches[0]?.clientY ?? startY) - startY
      startY = null
      if (!active) return
      active = false
      // Снимаем inline-трансформацию — управление возвращается CSS-классу:
      // открыт → translateY(0), после onClose класс убирается → translateY(100%).
      setTransform(null)
      if (dy > 110) onClose?.()
    }

    handle.addEventListener('touchstart', onStart, { passive: true })
    handle.addEventListener('touchmove', onMove, { passive: false })
    handle.addEventListener('touchend', onEnd, { passive: true })
    handle.addEventListener('touchcancel', onEnd, { passive: true })
    return () => {
      handle.removeEventListener('touchstart', onStart)
      handle.removeEventListener('touchmove', onMove)
      handle.removeEventListener('touchend', onEnd)
      handle.removeEventListener('touchcancel', onEnd)
    }
  }, [onClose])

  useLayoutEffect(() => {
    const nav = navRef.current
    if (!nav) return
    const active = nav.querySelector('.panel-nav-item-active')
    if (active) {
      setIndicator({ top: active.offsetTop, height: active.offsetHeight, visible: true })
    } else {
      setIndicator((p) => ({ ...p, visible: false }))
    }
  }, [activeSection, sections])

  useEffect(() => {
    const onResize = () => {
      const nav = navRef.current
      const active = nav?.querySelector('.panel-nav-item-active')
      if (active) setIndicator({ top: active.offsetTop, height: active.offsetHeight, visible: true })
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <aside
      ref={sidebarRef}
      className={`panel-shelf panel-shelf-sidebar${mobileOpen ? ' panel-sidebar-mobile-open' : ''}`}
    >
      {/* Ручка + крестик — только на мобильном bottom-sheet. Здесь и только здесь
          живёт свайп-вниз; крестик — гарантированный способ закрыть меню. */}
      <div className="panel-sidebar-grab" ref={grabRef}>
        <span className="panel-sidebar-grabber" aria-hidden="true" />
        <button
          type="button"
          className="panel-sidebar-close"
          aria-label="Закрыть меню"
          onClick={onClose}
        >
          ✕
        </button>
      </div>

      <div className="panel-sidebar-profile">
        <div className="panel-profile-avatar" aria-hidden="true">
          {photoUrl ? (
            <img className="panel-profile-photo" src={photoUrl} alt="" />
          ) : (
            <span className="panel-profile-initials">{initials}</span>
          )}
        </div>

        <div className="panel-profile-meta">
          <p className="panel-profile-kicker">
            {role === 'owner' ? '👑 Владелец' : 'Cute Epsilon'}
          </p>
          <h1 className="panel-profile-name">{displayName}</h1>
          {username && <p className="panel-profile-username">@{username}</p>}
        </div>
      </div>

      <nav className="panel-sidebar-nav" aria-label="Навигация панели" ref={navRef}>
        {indicator.visible && (
          <span
            className="panel-nav-indicator"
            style={{ transform: `translateY(${indicator.top}px)`, height: `${indicator.height}px` }}
            aria-hidden="true"
          />
        )}
        {sections.map((item) => {
          const active = item.id === activeSection
          const NavIcon = NAV_ICONS[item.id]
          return (
            <button
              key={item.id}
              type="button"
              className={`panel-nav-item${active ? ' panel-nav-item-active' : ''}`}
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
            </button>
          )
        })}
      </nav>

      <div className="panel-sidebar-footer">
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
          title={lightMode ? 'Режим HD — включить эффекты' : 'Лёгкий режим — убрать нагрузку'}
        >
          <span aria-hidden="true">{lightMode ? '◈' : '⬡'}</span>
          {lightMode ? 'Лёгкий режим' : 'Режим HD'}
        </button>
        <button type="button" className="panel-logout-btn" onClick={onLogout}>
          Выйти
        </button>
      </div>
    </aside>
  )
}
