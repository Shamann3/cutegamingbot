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

function SlidersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <line x1="4" y1="8" x2="20" y2="8" />
      <line x1="4" y1="16" x2="20" y2="16" />
      <circle cx="9" cy="8" r="2.2" fill="currentColor" stroke="none" />
      <circle cx="15" cy="16" r="2.2" fill="currentColor" stroke="none" />
    </svg>
  )
}

function shortLabel(text) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const word = raw.split(/\s+/)[0]
  return word.length > 12 ? `${word.slice(0, 11)}…` : word
}

/** Нижняя полоса в стиле CryptoBot: вкладки + меню (ползунки) справа на телефоне / слева на ПК. */
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
  const pivotAt = sections.findIndex((item) => item.id === 'moderation')
  const leftTabs = pivotAt >= 0 ? sections.slice(0, pivotAt) : sections
  const pivotTab = pivotAt >= 0 ? sections[pivotAt] : null
  const rightTabs = pivotAt >= 0 ? sections.slice(pivotAt + 1) : []

  const renderTab = useCallback((item) => {
    const Icon = NAV_ICONS[item.id] || FallbackIcon
    const on = item.id === activeSection
    const count = Number(badges[item.id] || 0)
    const mark = shortLabel(item.labelRu || item.label)
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
  }, [activeSection, badges, onNavigate])

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
      ) : pivotTab ? (
        <div className="phone-dock-scroll is-pivoted">
          <div className="phone-dock-side is-left">
            {leftTabs.map((item) => renderTab(item))}
          </div>
          <div className="phone-dock-pivot">{renderTab(pivotTab)}</div>
          <div className="phone-dock-side is-right">
            {rightTabs.map((item) => renderTab(item))}
          </div>
        </div>
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
          <span className="phone-dock-icon"><SlidersIcon /></span>
          <span className="phone-dock-label">Настройки</span>
        </button>
      )}
    </motion.nav>
  )
}
