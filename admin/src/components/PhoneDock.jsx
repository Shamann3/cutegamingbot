import { useEffect, useRef } from 'react'
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

/** Нижняя полоса: главные вкладки. На компьютере слева ещё меню. */
export default function PhoneDock({
  sections = [],
  activeSection,
  onNavigate,
  badges = {},
  onOpenMenu,
  menuOpen = false,
}) {
  const barRef = useRef(null)
  const activeRef = useRef(null)
  const crowded = sections.length > 6
  const reduce = useReducedMotion()

  useEffect(() => {
    const bar = barRef.current
    const node = activeRef.current
    if (!bar || !node) return
    const left = node.offsetLeft - (bar.clientWidth - node.offsetWidth) / 2
    bar.scrollTo({ left: Math.max(0, left), behavior: reduce ? 'auto' : 'smooth' })
  }, [activeSection, sections.length, reduce])

  if (!sections.length) return null

  return (
    <motion.nav
      className={`phone-dock${crowded ? ' is-crowded' : ''}`}
      data-coach="dock"
      aria-label="Вкладки"
      initial={reduce ? false : { y: 16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="phone-dock-scroll" ref={barRef}>
        {sections.map((item) => {
          const Icon = NAV_ICONS[item.id] || FallbackIcon
          const on = item.id === activeSection
          const count = Number(badges[item.id] || 0)
          const mark = String(item.labelRu || item.label || '').trim()
          return (
            <button
              key={item.id}
              type="button"
              ref={on ? activeRef : null}
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
        })}
      </div>
      {typeof onOpenMenu === 'function' && (
        <button
          type="button"
          className={`phone-dock-menu${menuOpen ? ' is-on' : ''}`}
          data-coach="menu"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Закрыть меню' : 'Поиск, цвет и выход'}
          onClick={onOpenMenu}
        >
          <SlidersIcon />
        </button>
      )}
    </motion.nav>
  )
}
