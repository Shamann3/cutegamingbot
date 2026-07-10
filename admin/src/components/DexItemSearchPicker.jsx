import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchContentDex, fetchDexItemFull } from '../lib/adminClient'

const PAGE_SIZE = 60
const MIN_QUERY = 1

function DexItemRow({ item, active, onPick }) {
  return (
    <button
      type="button"
      className={`dex-item-search-option${active ? ' dex-item-search-option-active' : ''}`}
      onClick={() => onPick(item)}
    >
      <span className="dex-item-search-option-emoji" aria-hidden>{item.emoji || '📦'}</span>
      <span className="dex-item-search-option-body">
        <span className="dex-item-search-option-name">{item.name}</span>
        {item.name1 ? (
          <span className="dex-item-search-option-name1">{item.name1}</span>
        ) : null}
      </span>
      <span className="dex-item-search-option-id">#{item.id}</span>
    </button>
  )
}

function SelectedPreview({ item, fallbackId = '' }) {
  if (!item) {
    return fallbackId ? (
      <span className="dex-item-search-selected-fallback">#{fallbackId}</span>
    ) : (
      <span className="dex-item-search-selected-empty">не выбрано</span>
    )
  }
  return (
    <span className="dex-item-search-selected">
      <span className="dex-item-search-selected-emoji" aria-hidden>{item.emoji || '📦'}</span>
      <span className="dex-item-search-selected-text">
        <span className="dex-item-search-selected-name">{item.name}</span>
        <span className="dex-item-search-selected-id">#{item.id}</span>
      </span>
    </span>
  )
}

export default function DexItemSearchPicker({
  label,
  value,
  onChange,
  disabled = false,
  scope = 'all',
  placeholder = 'Введите название или эмодзи…',
  hint = 'Поиск по всей таблице dex: название, name1, эмодзи, id',
}) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const listRef = useRef(null)

  const canSearch = query.trim().length >= MIN_QUERY

  const loadItems = useCallback(async (q, nextOffset = 0, append = false) => {
    const trimmed = q.trim()
    if (trimmed.length < MIN_QUERY) {
      setItems([])
      setTotal(0)
      setOffset(0)
      return
    }
    setLoading(true)
    try {
      const data = await fetchContentDex({
        q: trimmed,
        limit: PAGE_SIZE,
        offset: nextOffset,
        scope,
      })
      const batch = data.items || []
      setItems((prev) => (append ? [...prev, ...batch] : batch))
      setTotal(Number(data.total) || batch.length)
      setOffset(nextOffset + batch.length)
    } finally {
      setLoading(false)
    }
  }, [scope])

  useEffect(() => {
    if (!value) {
      setSelected(null)
      return undefined
    }
    let cancelled = false
    fetchDexItemFull(value)
      .then((item) => {
        if (!cancelled && item?.id) setSelected(item)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [value])

  useEffect(() => {
    if (!open || !canSearch) return undefined
    const timer = setTimeout(() => {
      loadItems(query, 0, false)
    }, 220)
    return () => clearTimeout(timer)
  }, [open, query, canSearch, loadItems])

  useEffect(() => {
    const onDocClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const hasMore = items.length < total

  const pickItem = (item) => {
    setSelected(item)
    onChange(String(item.id))
    setOpen(false)
    setQuery('')
    setItems([])
  }

  const clearItem = () => {
    setSelected(null)
    onChange('')
    setQuery('')
    setItems([])
  }

  const openPicker = () => {
    if (disabled) return
    setOpen((prev) => !prev)
  }

  const emptyHint = useMemo(() => {
    if (!canSearch) {
      return 'Введите хотя бы один символ — название или эмодзи предмета'
    }
    if (loading) return 'Поиск…'
    if (items.length === 0) return 'Ничего не найдено. Попробуйте другое название или эмодзи'
    return null
  }, [canSearch, loading, items.length])

  return (
    <div className="panel-economy-field dex-item-search-picker" ref={wrapRef}>
      <span className="dex-item-search-label">{label}</span>
      <button
        type="button"
        className="dex-item-search-current"
        disabled={disabled}
        onClick={openPicker}
        aria-expanded={open}
      >
        <SelectedPreview item={selected} fallbackId={value} />
        <span className="dex-item-search-caret" aria-hidden>{open ? '▲' : '▼'}</span>
      </button>
      {open && !disabled && (
        <div className="dex-item-search-dropdown">
          <div className="dex-item-search-search-row">
            <span className="dex-item-search-search-icon" aria-hidden>🔎</span>
            <input
              className="panel-users-input dex-item-search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              autoFocus
              aria-label={`Поиск: ${label}`}
            />
          </div>
          <p className="dex-item-search-hint">{hint}</p>
          <div className="dex-item-search-list" role="listbox" ref={listRef}>
            {emptyHint && (
              <p className="dex-item-search-muted">{emptyHint}</p>
            )}
            {items.map((item) => (
              <DexItemRow
                key={item.id}
                item={item}
                active={String(value) === String(item.id)}
                onPick={pickItem}
              />
            ))}
          </div>
          {hasMore && canSearch && !loading && (
            <button
              type="button"
              className="panel-users-btn dex-item-search-more"
              onClick={() => loadItems(query, offset, true)}
            >
              Показать ещё ({items.length} из {total})
            </button>
          )}
          {value && (
            <button type="button" className="panel-users-btn dex-item-search-clear" onClick={clearItem}>
              Сбросить выбор
            </button>
          )}
        </div>
      )}
    </div>
  )
}
