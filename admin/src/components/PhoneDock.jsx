import { useCallback } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { NAV_ICONS } from './NavIcons'

function FallbackIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="3" />
    </svg>
  )
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  )
}

function shortLabel(text) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const word = raw.split(/\s+/)[0]
  return word.length > 12 ? `${word.slice(0, 11)}…` : word
}

/** Нижняя полоса: главные вкладки одной группой по центру, настройки отдельно у края. */
export default function PhoneDock({
  sections = [],
  activeSection,
  onNavigate,
  badges = {},
  onOpenMenu,
  menuOpen = false,
  tabsInMenu = false,
}) {
  const crowded = sections.length > 5
  const reduce = useReducedMotion()
  const current = sections.find((item) => item.id === activeSection)
  const currentLabel = current?.labelRu || current?.label || 'Вкладки'

  const renderTab = useCallback((item) => {
    const Icon = NAV_ICONS[item.id] || FallbackIcon
    const on = item.id === activeSection
    const count = Number(badges[item.id] || 0)
    const mark = item.dockLabel || shortLabel(item.labelRu || item.label)
    return (
      <button
        key={item.id}
        type="button"
        className={on ? 'is-on' : ''}
        data-section={item.id}
        aria-label={item.labelRu || item.label}
        title={item.labelRu || item.label}
        aria-current={on ? 'page' : undefined}
        onClick={() => onNavigate(item.id)}
      >
        {on && (
          <motion.span
            className="phone-dock-pill"
            layoutId="phone-dock-pill"
            aria-hidden="true"
            transition={reduce || document.body.classList.contains('perf-light') ? { duration: 0 } : { type: 'spring', stiffness: 460, damping: 36, mass: 0.7 }}
          />
        )}
        <span className="phone-dock-icon">
          <Icon />
          {count > 0 && (
            <i className="phone-dock-badge">{count > 99 ? '99+' : count}</i>
          )}
        </span>
        {mark && <span className="phone-dock-label">{mark}</span>}
        <span className="phone-dock-mark" aria-hidden="true" />
      </button>
    )
  }, [activeSection, badges, onNavigate, reduce])

  if (!sections.length) return null

  return (
    <motion.nav
      className={`phone-dock${crowded ? ' is-crowded' : ''}${tabsInMenu ? ' is-tabs-menu' : ''}`}
      data-coach="dock"
      aria-label="Вкладки"
      initial={reduce ? false : { y: 16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      {tabsInMenu ? (
        <button
          type="button"
          className={`phone-dock-all${menuOpen ? ' is-on' : ''}`}
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Закрыть вкладки' : 'Все вкладки'}
          onClick={onOpenMenu}
        >
          <span>Вкладки</span>
          <b>{currentLabel}</b>
        </button>
      ) : (
        <div className="phone-dock-scroll">
          {sections.map((item) => renderTab(item))}
        </div>
      )}
      {typeof onOpenMenu === 'function' && !tabsInMenu && (
        <button
          type="button"
          className={`phone-dock-menu${menuOpen ? ' is-on' : ''}`}
          data-coach="menu"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Закрыть настройки' : 'Настройки панели'}
          onClick={onOpenMenu}
        >
          <span className="phone-dock-icon"><GearIcon /></span>
        </button>
      )}
    </motion.nav>
  )
}
