import { useEffect, useMemo, useRef, useState } from 'react'
import { NAV_ICONS } from './NavIcons'

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.6-3.6" />
    </svg>
  )
}

/** Поиск раздела для вкладок из «Ещё»: по центру сверху + плашка с именем вкладки. */
export default function ExtrasTopSearch({
  sections = [],
  activeSection,
  onNavigate,
  tabLabel = 'Дополнительно',
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(0)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)

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

  useEffect(() => { setCursor(0) }, [results.length])

  useEffect(() => {
    const onDocDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
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
    <div className="extras-top-search" ref={wrapRef}>
      {open && query.trim() && (
        <button
          type="button"
          className="extras-top-search-backdrop"
          aria-label="Закрыть поиск"
          onClick={() => setOpen(false)}
        />
      )}
      <span className="extras-tab-pill" title={tabLabel}>{tabLabel}</span>
      <label className="extras-hub-search extras-top-search-field">
        <span className="extras-hub-search-icon" aria-hidden="true">
          <SearchIcon />
        </span>
        <input
          ref={inputRef}
          className="extras-hub-search-field"
          type="text"
          inputMode="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Поиск раздела…"
          aria-label="Поиск раздела"
          enterKeyHint="search"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>

      {open && query.trim() && (
        <div className="extras-top-search-results" role="listbox">
          {results.map((s, i) => {
            const Icon = NAV_ICONS[s.id]
            return (
              <button
                key={s.id}
                type="button"
                role="option"
                aria-selected={i === cursor}
                className={`extras-top-search-item${i === cursor ? ' is-active' : ''}`}
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(s.id)}
              >
                <span className="extras-top-search-item-icon">{Icon && <Icon />}</span>
                <span className="extras-top-search-item-label">{s.labelRu}</span>
                <span className="extras-top-search-item-sub">{s.label}</span>
                {s.id === activeSection && (
                  <span className="extras-top-search-item-now">сейчас</span>
                )}
              </button>
            )
          })}
          {!results.length && (
            <p className="extras-top-search-empty">Ничего не найдено</p>
          )}
        </div>
      )}
    </div>
  )
}
