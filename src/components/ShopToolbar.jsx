import { useEffect, useState } from 'react'
import BottomSheet from './BottomSheet'

const DEFAULT_FILTER = 'all'
const DEFAULT_SORT_KEY = 'name:asc'

const PRICE_FILTERS = [
  { id: 'all', label: 'Все цены' },
  { id: 'sale', label: 'Со скидкой' },
]

const SORT_OPTIONS = [
  { sortBy: 'name', sortOrder: 'asc', label: 'Название: А → Я' },
  { sortBy: 'name', sortOrder: 'desc', label: 'Название: Я → А' },
  { sortBy: 'price', sortOrder: 'asc', label: 'Цена: по возрастанию' },
  { sortBy: 'price', sortOrder: 'desc', label: 'Цена: по убыванию' },
  { sortBy: 'remains', sortOrder: 'asc', label: 'Остаток: по возрастанию' },
  { sortBy: 'remains', sortOrder: 'desc', label: 'Остаток: по убыванию' },
]

function FilterIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M4 5h16l-6 7v6l-4 2v-8L4 5z" strokeLinejoin="round" />
    </svg>
  )
}

function SortIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M8 6v12M5 9l3-3 3 3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 6v12M13 9l3-3 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function sortKey(sortBy, sortOrder) {
  return `${sortBy}:${sortOrder}`
}

function SheetOption({ selected, label, onToggle }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
        className={`shop-sheet-option ${selected ? 'shop-sheet-option-selected' : ''}`}
      onClick={onToggle}
    >
      <span
        className={`shop-sheet-radio-dot ${selected ? 'shop-sheet-radio-dot-selected' : ''}`}
        aria-hidden
      />
      <span className="shop-sheet-option-label">{label}</span>
    </button>
  )
}

export default function ShopToolbar({
  priceFilter,
  sortBy,
  sortOrder,
  onPriceFilterChange,
  onSortChange,
  disabled = false,
  className = '',
}) {
  const [openSheet, setOpenSheet] = useState(null)
  const [draftFilter, setDraftFilter] = useState(priceFilter)
  const [draftSortKey, setDraftSortKey] = useState(sortKey(sortBy, sortOrder))

  useEffect(() => {
    if (openSheet !== 'filter') setDraftFilter(priceFilter)
  }, [openSheet, priceFilter])

  useEffect(() => {
    if (openSheet !== 'sort') setDraftSortKey(sortKey(sortBy, sortOrder))
  }, [openSheet, sortBy, sortOrder])

  const closeSheet = () => setOpenSheet(null)

  const toggleFilter = (filterId) => {
    setDraftFilter((prev) => (prev === filterId ? null : filterId))
  }

  const toggleSort = (key) => {
    setDraftSortKey((prev) => (prev === key ? null : key))
  }

  const applyFilter = async () => {
    const nextFilter = draftFilter ?? DEFAULT_FILTER
    closeSheet()
    if (nextFilter !== priceFilter) {
      await onPriceFilterChange(nextFilter)
    }
  }

  const applySort = async () => {
    const key = draftSortKey ?? DEFAULT_SORT_KEY
    const [nextSortBy, nextSortOrder] = key.split(':')
    closeSheet()
    await onSortChange(nextSortBy, nextSortOrder)
  }

  const filterActive = priceFilter !== DEFAULT_FILTER
  const sortActive = sortBy !== 'name' || sortOrder !== 'asc'

  return (
    <>
      <div className={`shop-toolbar ${className}`.trim()} role="toolbar" aria-label="Фильтры и сортировка">
        <button
          type="button"
          className={`shop-tool-btn ${filterActive ? 'shop-tool-btn-active' : ''}`}
          disabled={disabled}
          aria-label="Фильтр по цене"
          aria-pressed={filterActive}
          onClick={() => setOpenSheet('filter')}
        >
          <FilterIcon />
        </button>
        <button
          type="button"
          className={`shop-tool-btn ${sortActive ? 'shop-tool-btn-active' : ''}`}
          disabled={disabled}
          aria-label="Сортировка"
          aria-pressed={sortActive}
          onClick={() => setOpenSheet('sort')}
        >
          <SortIcon />
        </button>
      </div>

      <BottomSheet
        isOpen={openSheet === 'filter'}
        onClose={closeSheet}
        title="Фильтр по цене"
        onApply={applyFilter}
      >
        <div className="shop-sheet-options" role="radiogroup" aria-label="Фильтр по цене">
          {PRICE_FILTERS.map((filter) => (
            <SheetOption
              key={filter.id}
              selected={draftFilter === filter.id}
              label={filter.label}
              onToggle={() => toggleFilter(filter.id)}
            />
          ))}
        </div>
      </BottomSheet>

      <BottomSheet
        isOpen={openSheet === 'sort'}
        onClose={closeSheet}
        title="Сортировка"
        onApply={applySort}
      >
        <div className="shop-sheet-options" role="radiogroup" aria-label="Сортировка">
          {SORT_OPTIONS.map((option) => {
            const key = sortKey(option.sortBy, option.sortOrder)
            return (
              <SheetOption
                key={key}
                selected={draftSortKey === key}
                label={option.label}
                onToggle={() => toggleSort(key)}
              />
            )
          })}
        </div>
      </BottomSheet>
    </>
  )
}
