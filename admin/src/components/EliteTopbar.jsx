import { useEffect, useMemo, useRef, useState } from 'react'
import { getAdminProfile } from '../lib/adminProfile'
import { NAV_ICONS } from './NavIcons'
import EpsilonLogo from './EpsilonLogo'

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.6-3.6" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8a6 6 0 1 0-12 0c0 6-2 7-2 7h16s-2-1-2-7" />
      <path d="M13.7 20a2 2 0 0 1-3.4 0" />
    </svg>
  )
}

function MenuIcon({ open }) {
  return (
    <span
      className={`panel-hamburger-icon${open ? ' panel-hamburger-icon-open' : ''}`}
      aria-hidden="true"
    />
  )
}

/** Приветствие по времени суток — панель открывают в любую смену,
 *  и «Добрый вечер» в 3 ночи выглядело бы небрежно. */
function greetingFor(hour) {
  if (hour < 5) return 'Доброй ночи'
  if (hour < 12) return 'Доброе утро'
  if (hour < 18) return 'Добрый день'
  return 'Добрый вечер'
}

/** Шапка панели: приветствие, быстрый переход по разделам, уведомления.
 *
 *  Поиск — не декорация: это переключатель разделов. Печатаешь часть
 *  названия (русского или английского), стрелки/Enter — переход.
 *  Открывается и с клавиатуры: Ctrl/Cmd+K.
 *
 *  На телефоне — название слева; поддержка и меню справа, меню в правом верхнем углу. */
export default function EliteTopbar({
  sections = [],
  activeSection,
  onNavigate,
  openTickets = 0,
  onOpenNotifications,
  onOpenMenu,
  menuOpen = false,
  /** Полное «С возвращением» — только на Главной.
   *  Сама шапка всегда compact — поиск стоит как на «Игроки». */
  compact = true,
  welcome = false,
  where = 'Панель сотрудника. Это весь проект, не одна группа.',
  showSupport = true,
  /** Скрыть поиск в шапке (вкладки «Ещё» — поиск в контенте). */
  hideSearch = false,
}) {
  const { displayName } = getAdminProfile()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(0)
  const [bellFresh, setBellFresh] = useState(false)
  const seenTickets = useRef(null)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    const next = Number(openTickets) || 0
    if (seenTickets.current == null) {
      seenTickets.current = next
      setBellFresh(next > 0)
      return
    }
    if (next > seenTickets.current) setBellFresh(true)
    if (next === 0) setBellFresh(false)
    seenTickets.current = next
  }, [openTickets])

  const greeting = useMemo(() => greetingFor(new Date().getHours()), [])
  const firstName = (displayName || '').trim().split(/\s+/)[0] || 'коллега'

  const activeMeta = useMemo(
    () => sections.find((s) => s.id === activeSection) || null,
    [sections, activeSection],
  )
  const sectionTitle = activeMeta?.labelRu || 'Панель'

  const results = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/ё/g, 'е')
    if (!q) return []
    return sections
      .filter((s) => {
        const ru = (s.labelRu || '').toLowerCase().replace(/ё/g, 'е')
        const en = (s.label || '').toLowerCase()
        const id = (s.id || '').toLowerCase()
        return ru.includes(q) || en.includes(q) || id.includes(q)
      })
      .slice(0, 8)
  }, [query, sections])

  // Курсор сбрасываем при смене выдачи, иначе он мог указывать за её пределы.
  useEffect(() => { setCursor(0) }, [results.length])

  useEffect(() => {
    const onDocDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
  }, [])

  useEffect(() => {
    if (hideSearch) return undefined
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hideSearch])

  const go = (id) => {
    onNavigate?.(id)
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      setQuery('')
      setOpen(false)
      inputRef.current?.blur()
      return
    }
    if (!results.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => (c + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => (c - 1 + results.length) % results.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      go(results[cursor].id)
    }
  }

  return (
    <div className={`elite-topbar${compact ? ' elite-topbar-compact' : ''}`}>
      <div className="elite-brand-slot" title="Epsilon Command" aria-label="Epsilon">
        <span className="elite-brand-slot-ring" aria-hidden="true" />
        <EpsilonLogo size="sm" decorative />
      </div>

      <div className="elite-greeting elite-greeting-desktop">
        {welcome ? (
          <>
            <span className="elite-greeting-kicker">{greeting}, {firstName}</span>
            <h1 className="elite-greeting-title">
              С возвращением
            </h1>
          </>
        ) : (
          <h1 className="elite-greeting-title elite-greeting-title-compact">
            {greeting}, {firstName}
          </h1>
        )}
      </div>

      <div className="elite-mobile-title">
        <h1 className="elite-mobile-section">{sectionTitle}</h1>
        <p className="elite-where">{where}</p>
      </div>

      <div className="elite-topbar-actions">
        {!hideSearch && (
          <div className="elite-search-wrap" data-coach="search" ref={wrapRef}>
            <div className="elite-search">
              <SearchIcon />
              <input
                ref={inputRef}
                className="elite-search-field"
                type="text"
                inputMode="search"
                enterKeyHint="search"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                value={query}
                placeholder="Поиск раздела…"
                aria-label="Поиск раздела"
                onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
                onFocus={() => setOpen(true)}
                onKeyDown={onKeyDown}
              />
            </div>

            {open && query.trim() && (
              <div className="elite-search-results" role="listbox">
                {results.map((s, i) => {
                  const Icon = NAV_ICONS[s.id]
                  return (
                    <button
                      key={s.id}
                      type="button"
                      role="option"
                      aria-selected={i === cursor}
                      className={`elite-search-item${i === cursor ? ' elite-search-item-active' : ''}`}
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => go(s.id)}
                    >
                      <span className="elite-search-item-icon">{Icon && <Icon />}</span>
                      <span className="elite-search-item-label">{s.labelRu}</span>
                      <span className="elite-search-item-sub">{s.label}</span>
                      {s.id === activeSection && (
                        <span className="elite-search-item-now">сейчас</span>
                      )}
                    </button>
                  )
                })}
                {!results.length && (
                  <p className="elite-search-empty">Ничего не найдено</p>
                )}
              </div>
            )}
          </div>
        )}

        {showSupport && <button
          type="button"
          className={`elite-icon-btn elite-support-btn${bellFresh ? ' is-fresh' : ''}`}
          aria-label={openTickets > 0
            ? `Поддержка, новых обращений: ${openTickets}`
            : 'Поддержка'}
          title={openTickets > 0 ? `Новых обращений: ${openTickets}` : 'Поддержка'}
          onClick={() => {
            setBellFresh(false)
            onOpenNotifications?.()
          }}
        >
          <BellIcon />
          {openTickets > 0 && (
            <span className={`elite-bell-count${bellFresh ? ' is-fresh' : ''}`}>
              {openTickets > 99 ? '99+' : openTickets}
            </span>
          )}
        </button>}

        {typeof onOpenMenu === 'function' && (
          <button
            type="button"
            className={`elite-menu-btn${menuOpen ? ' elite-menu-btn-open' : ''}`}
            data-coach="menu"
            aria-label={menuOpen ? 'Закрыть настройки' : 'Настройки панели'}
            aria-expanded={menuOpen}
            onClick={onOpenMenu}
          >
            <MenuIcon open={menuOpen} />
            <span className="elite-menu-label">{menuOpen ? 'Закрыть' : 'Настройки'}</span>
          </button>
        )}
      </div>
    </div>
  )
}
