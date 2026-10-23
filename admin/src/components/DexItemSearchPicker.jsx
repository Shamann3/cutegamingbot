import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { fetchContentDex, fetchDexItemFull } from '../lib/adminClient'

const PAGE_SIZE = 80

function fold(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .trim()
}

function valueOf(item, valueMode) {
  if (!item) return ''
  return valueMode === 'name' ? String(item.name || '') : String(item.id)
}

function matchesValue(item, value, valueMode) {
  if (!item || value == null || value === '') return false
  if (valueMode === 'name') {
    return item.name === value || item.name1 === value
  }
  return String(item.id) === String(value)
}

function DexItemRow({ item, active, onPick }) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      className={`dex-item-search-option${active ? ' dex-item-search-option-active' : ''}`}
      onClick={() => onPick(item)}
    >
      <span className="dex-item-search-option-emoji" aria-hidden>{item.emoji || '📦'}</span>
      <span className="dex-item-search-option-body">
        <span className="dex-item-search-option-name">{item.name}</span>
        <span className="dex-item-search-option-meta">
          {item.name1 ? <span className="dex-item-search-option-name1">{item.name1}</span> : null}
          {Number(item.price) > 0 ? <span className="dex-item-search-option-price">{item.price} кут</span> : null}
        </span>
      </span>
      <span className="dex-item-search-option-id">#{item.id}</span>
    </button>
  )
}

function SelectedPreview({ item, fallback = '', emptyLabel }) {
  if (!item) {
    if (fallback) {
      return (
        <span className="dex-item-search-selected">
          <span className="dex-item-search-selected-emoji" aria-hidden>📦</span>
          <span className="dex-item-search-selected-text">
            <span className="dex-item-search-selected-name">{fallback}</span>
            <span className="dex-item-search-selected-id">ещё без карточки в списке</span>
          </span>
        </span>
      )
    }
    return <span className="dex-item-search-selected-empty">{emptyLabel}</span>
  }
  return (
    <span className="dex-item-search-selected">
      <span className="dex-item-search-selected-emoji" aria-hidden>{item.emoji || '📦'}</span>
      <span className="dex-item-search-selected-text">
        <span className="dex-item-search-selected-name">{item.name}</span>
        <span className="dex-item-search-selected-id">
          #{item.id}{item.name1 ? ` · ${item.name1}` : ''}
        </span>
      </span>
    </span>
  )
}

function filterCatalog(catalog, q) {
  const needle = fold(q)
  const rows = Array.isArray(catalog) ? catalog : []
  if (!needle) return rows
  return rows.filter((item) => {
    const hay = fold(`${item.emoji || ''} ${item.name || ''} ${item.name1 || ''} ${item.id || ''}`)
    return hay.includes(needle) || String(item.emoji || '') === String(q || '').trim()
  })
}

function findInCatalog(catalog, value, valueMode) {
  const raw = String(value || '').trim()
  if (!raw) return null
  const rows = Array.isArray(catalog) ? catalog : []
  if (valueMode === 'name') {
    return (
      rows.find((row) => row.name === raw)
      || rows.find((row) => row.name1 === raw)
      || rows.find((row) => fold(row.name) === fold(raw))
      || null
    )
  }
  return rows.find((row) => String(row.id) === raw) || null
}

async function resolveSelected(value, valueMode, catalog) {
  const raw = String(value || '').trim()
  if (!raw) return null
  const local = findInCatalog(catalog, raw, valueMode)
  if (local) return local
  if (Array.isArray(catalog) && catalog.length > 0) {
    return valueMode === 'name'
      ? { id: '', name: raw, name1: '', emoji: '📦', price: 0 }
      : null
  }
  if (valueMode === 'id') {
    try {
      const item = await fetchDexItemFull(raw)
      return item?.id ? item : null
    } catch {
      return null
    }
  }
  try {
    const data = await fetchContentDex({ q: raw, limit: 40, offset: 0 })
    const batch = data.items || []
    return (
      batch.find((row) => row.name === raw)
      || batch.find((row) => row.name1 === raw)
      || batch.find((row) => fold(row.name) === fold(raw))
      || null
    )
  } catch {
    return null
  }
}

export default function DexItemSearchPicker({
  label,
  value,
  onChange,
  disabled = false,
  scope = 'all',
  placeholder = 'Название, эмодзи или id…',
  hint = 'Поиск по всей таблице dex: название, name1, эмодзи, id. Пустой поиск — весь каталог.',
  valueMode = 'id',
  clearable = true,
  emptyLabel = 'Не выбрано',
  compact = false,
  className = '',
  catalog = null,
}) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [menuStyle, setMenuStyle] = useState({})
  const wrapRef = useRef(null)
  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)
  const inputRef = useRef(null)
  const listId = useId()
  const localCatalog = Array.isArray(catalog) ? catalog : null

  const loadItems = useCallback(async (q, nextOffset = 0, append = false) => {
    if (localCatalog) {
      const filtered = filterCatalog(localCatalog, q)
      const batch = filtered.slice(nextOffset, nextOffset + PAGE_SIZE)
      setItems((prev) => (append ? [...prev, ...batch] : batch))
      setTotal(filtered.length)
      setOffset(nextOffset + batch.length)
      setActiveIndex(0)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await fetchContentDex({
        q: String(q || '').trim(),
        limit: PAGE_SIZE,
        offset: nextOffset,
        scope,
      })
      const batch = data.items || []
      setItems((prev) => (append ? [...prev, ...batch] : batch))
      setTotal(Number(data.total) || batch.length)
      setOffset(nextOffset + batch.length)
      setActiveIndex(0)
    } finally {
      setLoading(false)
    }
  }, [scope, localCatalog])

  useEffect(() => {
    let cancelled = false
    if (!value) {
      setSelected(null)
      return undefined
    }
    resolveSelected(value, valueMode, localCatalog).then((item) => {
      if (!cancelled) setSelected(item)
    })
    return () => { cancelled = true }
  }, [value, valueMode, localCatalog])

  useEffect(() => {
    if (!open) return undefined
    const timer = setTimeout(() => {
      loadItems(query, 0, false)
    }, query.trim() ? 180 : 0)
    return () => clearTimeout(timer)
  }, [open, query, loadItems])

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const width = Math.max(rect.width, compact ? 280 : 320)
    const maxHeight = Math.min(420, window.innerHeight - 24)
    const spaceBelow = window.innerHeight - rect.bottom
    const openUp = spaceBelow < Math.min(320, maxHeight) && rect.top > spaceBelow
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8)
    setMenuStyle({
      position: 'fixed',
      zIndex: 10050,
      left,
      width,
      maxHeight,
      ...(openUp
        ? { bottom: window.innerHeight - rect.top + 6 }
        : { top: rect.bottom + 6 }),
    })
  }, [compact])

  useLayoutEffect(() => {
    if (!open) return undefined
    updateMenuPosition()
    const onReposition = () => updateMenuPosition()
    window.addEventListener('resize', onReposition)
    window.addEventListener('scroll', onReposition, true)
    return () => {
      window.removeEventListener('resize', onReposition)
      window.removeEventListener('scroll', onReposition, true)
    }
  }, [open, updateMenuPosition, items.length, loading])

  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      const target = event.target
      if (wrapRef.current?.contains(target)) return
      if (dropdownRef.current?.contains(target)) return
      setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('touchstart', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('touchstart', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(() => {
    if (open) {
      const timer = setTimeout(() => inputRef.current?.focus(), 20)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [open])

  const hasMore = items.length < total

  const pickItem = (item) => {
    setSelected(item)
    onChange(valueOf(item, valueMode))
    setOpen(false)
    setQuery('')
  }

  const clearItem = () => {
    setSelected(null)
    onChange('')
    setQuery('')
    setItems([])
    setOpen(false)
  }

  const openPicker = () => {
    if (disabled) return
    setOpen((prev) => !prev)
  }

  const emptyHint = useMemo(() => {
    if (loading && items.length === 0) return 'Загружаем каталог…'
    if (!loading && items.length === 0) {
      return query.trim()
        ? 'Ничего не найдено. Попробуйте другое название или эмодзи'
        : 'В каталоге пока пусто'
    }
    return null
  }, [loading, items.length, query])

  const onInputKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => Math.min(items.length - 1, index + 1))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(0, index - 1))
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const item = items[activeIndex]
      if (item) pickItem(item)
    }
  }

  const dropdown = open && !disabled
    ? createPortal(
      <div
        className={`dex-item-search-dropdown${compact ? ' is-compact' : ''}`}
        style={menuStyle}
        ref={dropdownRef}
        role="presentation"
      >
        <div className="dex-item-search-search-row">
          <span className="dex-item-search-search-icon" aria-hidden>🔎</span>
          <input
            ref={inputRef}
            className="panel-users-input dex-item-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder={placeholder}
            aria-label={label ? `Поиск: ${label}` : 'Поиск предмета'}
            aria-controls={listId}
            aria-autocomplete="list"
          />
          {query ? (
            <button
              type="button"
              className="dex-item-search-query-clear"
              onClick={() => setQuery('')}
              aria-label="Очистить поиск"
            >
              ×
            </button>
          ) : null}
        </div>
        <p className="dex-item-search-hint">
          {hint}
          {total > 0 ? ` · найдено ${total}` : ''}
          {loading ? ' · обновляем…' : ''}
        </p>
        <div className="dex-item-search-list" role="listbox" id={listId}>
          {emptyHint && <p className="dex-item-search-muted">{emptyHint}</p>}
          {items.map((item, index) => (
            <DexItemRow
              key={`${item.id}-${item.name}`}
              item={item}
              active={matchesValue(item, value, valueMode) || index === activeIndex}
              onPick={pickItem}
            />
          ))}
        </div>
        {hasMore && !loading && (
          <button
            type="button"
            className="panel-users-btn dex-item-search-more"
            onClick={() => loadItems(query, offset, true)}
          >
            Показать ещё ({items.length} из {total})
          </button>
        )}
        {clearable && value ? (
          <button type="button" className="panel-users-btn dex-item-search-clear" onClick={clearItem}>
            Сбросить выбор
          </button>
        ) : null}
      </div>,
      document.body,
    )
    : null

  return (
    <div
      className={`panel-economy-field dex-item-search-picker${compact ? ' is-compact' : ''}${className ? ` ${className}` : ''}`}
      ref={wrapRef}
    >
      {label ? <span className="dex-item-search-label">{label}</span> : null}
      <button
        type="button"
        className="dex-item-search-current"
        disabled={disabled}
        onClick={openPicker}
        aria-expanded={open}
        aria-haspopup="listbox"
        ref={triggerRef}
      >
        <SelectedPreview
          item={selected}
          fallback={value && !selected ? String(value) : ''}
          emptyLabel={emptyLabel}
        />
        <span className="dex-item-search-caret" aria-hidden>{open ? '▲' : '▼'}</span>
      </button>
      {dropdown}
    </div>
  )
}
