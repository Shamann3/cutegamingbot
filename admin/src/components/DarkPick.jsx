import { useEffect, useId, useMemo, useRef, useState } from 'react'

/** Список внутри панели. Системное меню select на телефоне белое и не красится. */
export default function DarkPick({
  label,
  value,
  placeholder = 'Выберите',
  options = [],
  onChange,
  searchable = null,
  searchPlaceholder = 'Поиск…',
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const listId = useId()
  const current = options.find((item) => String(item.value) === String(value)) || null
  const withSearch = searchable == null ? options.length > 8 : Boolean(searchable)

  const filtered = useMemo(() => {
    const needle = String(query || '').toLowerCase().replace(/ё/g, 'е').trim()
    if (!needle) return options
    return options.filter((item) => {
      const hay = `${item.label || ''} ${item.hint || ''} ${item.value || ''}`.toLowerCase().replace(/ё/g, 'е')
      return hay.includes(needle)
    })
  }, [options, query])

  useEffect(() => {
    if (!open) {
      setQuery('')
      return undefined
    }
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    const focusTimer = setTimeout(() => inputRef.current?.focus(), 20)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
      clearTimeout(focusTimer)
    }
  }, [open])

  return (
    <div className={`dark-pick${open ? ' is-open' : ''}`} ref={rootRef}>
      {label ? <span className="dark-pick-label">{label}</span> : null}
      <button
        type="button"
        className="dark-pick-btn"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((next) => !next)}
      >
        <span>{current ? current.label : placeholder}</span>
        <i aria-hidden="true" />
      </button>
      {open && (
        <div className="dark-pick-panel">
          {withSearch && (
            <div className="dark-pick-search">
              <span aria-hidden>🔎</span>
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={searchPlaceholder}
                aria-label={label ? `Поиск: ${label}` : 'Поиск'}
              />
            </div>
          )}
          <ul className="dark-pick-list" id={listId} role="listbox">
            {filtered.length === 0 && <li className="dark-pick-empty">Ничего не найдено</li>}
            {filtered.map((item) => {
              const on = String(item.value) === String(value)
              return (
                <li key={item.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={on}
                    className={on ? 'is-on' : ''}
                    onClick={() => {
                      onChange(String(item.value))
                      setOpen(false)
                    }}
                  >
                    <strong>{item.label}</strong>
                    {item.hint ? <span>{item.hint}</span> : null}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
