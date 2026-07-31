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
 *  Открывается и с клавиатуры: Ctrl/Cmd+K. */
export default function EliteTopbar({
  sections = [],
  activeSection,
  onNavigate,
  openTickets = 0,
  onOpenNotifications,
  /** Полное «С возвращением» — только на Главной. На остальных разделах
   *  компактная строка, иначе приветствие конкурирует с sec-title. */
  compact = false,
}) {
  const { displayName } = getAdminProfile()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(0)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)

  const greeting = useMemo(() => greetingFor(new Date().getHours()), [])
  const firstName = (displayName || '').trim().split(/\s+/)[0] || 'коллега'

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return sections
      .filter((s) =>
        s.labelRu.toLowerCase().includes(q) || s.label.toLowerCase().includes(q))
      .slice(0, 6)
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
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

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
      <div className="elite-brand-slot" aria-hidden="true" title="Cute Epsilon">
        <EpsilonLogo size="sm" decorative />
      </div>
      <div className="elite-greeting">
        {compact ? (
          <h1 className="elite-greeting-title elite-greeting-title-compact">
            {greeting}, {firstName}
          </h1>
        ) : (
          <>
            <span className="elite-greeting-kicker">{greeting}, {firstName}</span>
            <h1 className="elite-greeting-title">
              С возвращением
              <span className="elite-wave" aria-hidden="true">👋</span>
            </h1>
          </>
        )}
      </div>

      <div className="elite-topbar-actions">
        {/* Колокольчик слева от поиска — не под системным ✕ Telegram WebApp */}
        <button
          type="button"
          className="elite-icon-btn"
          aria-label={openTickets > 0
            ? `Открытых обращений: ${openTickets}`
            : 'Уведомлений нет'}
          title={openTickets > 0
            ? `${openTickets} открытых обращений`
            : 'Уведомлений нет'}
          onClick={onOpenNotifications}
        >
          <BellIcon />
          {openTickets > 0 && <span className="elite-bell-dot" aria-hidden="true" />}
        </button>

        <div className="elite-search-wrap" ref={wrapRef}>
          <div className="elite-search">
            <SearchIcon />
            <input
              ref={inputRef}
              type="text"
              value={query}
              placeholder="Поиск раздела…"
              aria-label="Поиск раздела"
              onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              onKeyDown={onKeyDown}
            />
            {!query && <kbd className="elite-kbd">⌘K</kbd>}
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
      </div>
    </div>
  )
}
