import { useMemo, useState } from 'react'
import FarmBackground from './FarmBackground'
import VineFrame from './VineFrame'
import KutBalance from './KutBalance'
import DonateModal from './DonateModal'
import InventoryItemModal from './InventoryItemModal'
import TabAtmosphere from './TabAtmosphere'
import { useInventory } from '../hooks/useInventory'
import { formatKut } from '../utils/formatKut'
import { inventoryTileHint } from '../utils/inventoryEconomy'

const FILTERS = [
  { id: 'all', label: 'Все', emoji: '🎒' },
  { id: 'farm', label: 'Ферма', emoji: '🌾' },
  { id: 'gear', label: 'Инструменты', emoji: '🪓' },
  { id: 'other', label: 'Прочее', emoji: '📦' },
]

function errorClass(code) {
  if (code === 'auth') return 'inventory-toast-auth'
  if (code === 'rate_limit') return 'inventory-toast-rate'
  if (code === 'maintenance') return 'inventory-toast-maint'
  return 'inventory-toast-error'
}

export default function InventoryModule({ isActive = true }) {
  const {
    kut,
    items,
    summary,
    initialLoading,
    refreshing,
    error,
    errorCode,
  } = useInventory({ isActive })

  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')
  const [selectedItem, setSelectedItem] = useState(null)
  const [donateOpen, setDonateOpen] = useState(false)

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase()
    return items.filter((item) => {
      if (activeFilter !== 'all' && item.group !== activeFilter) return false
      if (!query) return true
      return (
        item.name.toLowerCase().includes(query)
        || item.categoryLabel.toLowerCase().includes(query)
        || item.id.includes(query)
      )
    })
  }, [items, search, activeFilter])

  const filterCounts = useMemo(() => {
    const counts = { all: items.length, farm: 0, gear: 0, other: 0 }
    items.forEach((item) => {
      if (counts[item.group] != null) counts[item.group] += 1
    })
    return counts
  }, [items])

  return (
    <div className="relative min-h-screen tab-theme-inventory inventory-module">
      <FarmBackground />
      <TabAtmosphere variant="inventory" />

      <div className="relative z-10 inventory-shell py-4 pb-2 animate-slide-up">
        <header className="inventory-hero">
          <div className="inventory-hero-copy">
            <p className="inventory-hero-eyebrow">Cute</p>
            <h1 className="inventory-hero-title">Инвентарь</h1>
          </div>
          <KutBalance
            value={kut}
            className="inventory-hero-balance"
            onDonate={() => setDonateOpen(true)}
          />
        </header>

        <div className="inventory-summary" role="status">
          <span className="inventory-summary-chip">
            {formatKut(summary.totalKinds)} {summary.totalKinds === 1 ? 'вид' : summary.totalKinds < 5 ? 'вида' : 'видов'}
          </span>
          <span className="inventory-summary-chip">
            {formatKut(summary.totalCount)} шт всего
          </span>
        </div>

        <label className="inventory-search">
          <span className="inventory-search-icon" aria-hidden>🔎</span>
          <input
            type="search"
            className="inventory-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Найти предмет…"
            aria-label="Поиск в рюкзаке"
          />
          {search ? (
            <button
              type="button"
              className="inventory-search-clear"
              onClick={() => setSearch('')}
              aria-label="Очистить поиск"
            >
              ✕
            </button>
          ) : null}
        </label>

        <div className="inventory-filters" role="toolbar" aria-label="Фильтр предметов">
          {FILTERS.map((filter) => (
            <button
              key={filter.id}
              type="button"
              className={`inventory-filter-chip ${activeFilter === filter.id ? 'inventory-filter-chip-active' : ''}`}
              onClick={() => setActiveFilter(filter.id)}
            >
              <span aria-hidden>{filter.emoji}</span>
              <span>{filter.label}</span>
              <span className="inventory-filter-count">{filterCounts[filter.id] ?? 0}</span>
            </button>
          ))}
        </div>

        {error ? (
          <p className={`inventory-toast ${errorClass(errorCode)}`} role="alert">
            {error}
          </p>
        ) : null}

        <VineFrame className="inventory-board-frame">
          <section
            id="onboarding-backpack"
            className="inventory-board"
            aria-label="Предметы в рюкзаке"
          >
            {initialLoading ? (
              <div className="inventory-skeleton-grid" aria-hidden>
                {Array.from({ length: 8 }, (_, index) => (
                  <div key={index} className="inventory-skeleton-tile" />
                ))}
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="inventory-empty">
                <span className="inventory-empty-icon" aria-hidden>🎒</span>
                <p>
                  {items.length === 0
                    ? 'Рюкзак пуст. Соберите урожай или загляните в магазин'
                    : 'Ничего не найдено по фильтру'}
                </p>
              </div>
            ) : (
              <div className={`inventory-grid ${refreshing ? 'inventory-grid-refresh' : ''}`}>
                {filteredItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="inventory-tile"
                    onClick={() => setSelectedItem(item)}
                    aria-label={`${item.name}, ${item.count} шт`}
                  >
                    <span className="inventory-tile-emoji" aria-hidden>{item.emoji}</span>
                    <span className="inventory-tile-name">{item.name}</span>
                    <span className="inventory-tile-qty">×{formatKut(item.count)}</span>
                    <span className="inventory-tile-meta">{inventoryTileHint(item)}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        </VineFrame>
      </div>

      <InventoryItemModal
        item={selectedItem}
        isOpen={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
      />

      <DonateModal isOpen={donateOpen} onClose={() => setDonateOpen(false)} />
    </div>
  )
}
