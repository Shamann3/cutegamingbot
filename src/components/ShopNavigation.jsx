import { useEffect, useMemo, useState } from 'react'

const EMPTY_MESSAGES = [
  'К сожалению, предметов сейчас нет в наличии',
  'Извините, этот товар отсутствует',
  'Сейчас нет в наличии',
  'К сожалению, товар закончился',
]

function pickEmptyMessage(categoryId) {
  if (categoryId && categoryId !== 'all') {
    const idx = Math.abs(categoryId.split('').reduce((a, c) => a + c.charCodeAt(0), 0))
    return EMPTY_MESSAGES[idx % EMPTY_MESSAGES.length]
  }
  return 'В каталоге сейчас нет предметов в наличии. Пожалуйста, загляните позже'
}

function ChevronIcon({ direction = 'left', double = false }) {
  if (double) {
    const paths =
      direction === 'left'
        ? ['M13 6l-6 6 6 6', 'M19 6l-6 6 6 6']
        : ['M5 6l6 6-6 6', 'M11 6l6 6-6 6']
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
        {paths.map((path) => (
          <path key={path} d={path} strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
    )
  }

  const path = direction === 'left' ? 'M15 6l-6 6 6 6' : 'M9 6l6 6-6 6'
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d={path} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function ShopNavigation({
  sortFilters = [],
  activeCategory,
  page,
  totalPages,
  totalItems,
  disabled,
  onSelectSort,
  onResetSort,
  onGoToPage,
  className = '',
  ariaLabel = 'Управление магазином',
  categoriesLabel = 'Категории',
  allChipEmoji = '🏪',
}) {
  const showPagination = totalPages > 1
  const isFiltered = activeCategory !== 'all'
  const [pageText, setPageText] = useState(String(page + 1))

  useEffect(() => {
    setPageText(String(page + 1))
  }, [page])

  const categoryChips = useMemo(
    () => [
      {
        id: 'all',
        label: 'Все',
        emoji: allChipEmoji,
        count: null,
        isActive: !isFiltered,
        disabled: false,
        onClick: onResetSort,
      },
      ...sortFilters.map((filter) => ({
        id: filter.id,
        label: filter.label,
        emoji: filter.emoji,
        count: filter.count,
        isActive: activeCategory === filter.id || activeCategory === filter.sorting,
        disabled: filter.count < 1,
        onClick: () => onSelectSort(filter.id),
      })),
    ],
    [sortFilters, isFiltered, activeCategory, onResetSort, onSelectSort, allChipEmoji],
  )

  const applyPageJump = () => {
    const parsed = Number.parseInt(pageText, 10)
    if (!Number.isFinite(parsed)) {
      setPageText(String(page + 1))
      return
    }

    const nextPage = Math.min(Math.max(parsed, 1), totalPages) - 1
    setPageText(String(nextPage + 1))
    if (nextPage !== page) onGoToPage(nextPage)
  }

  const handlePageInput = (event) => {
    const raw = event.target.value
    if (raw === '') {
      setPageText('')
      return
    }
    if (/^\d+$/.test(raw)) setPageText(raw)
  }

  return (
    <nav className={`shop-nav ${className}`.trim()} aria-label={ariaLabel}>
      <div className="shop-nav-section">
        <p className="shop-nav-caption">{categoriesLabel}</p>
        <div className="shop-nav-chips" role="toolbar" aria-label="Фильтр по категории">
          {categoryChips.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={`shop-nav-chip ${chip.isActive ? 'shop-nav-chip-active' : ''}`}
              disabled={disabled || chip.disabled}
              title={chip.count != null ? `${chip.label} (${chip.count})` : chip.label}
              aria-pressed={chip.isActive}
              onClick={chip.onClick}
            >
              <span className="shop-nav-chip-emoji" aria-hidden>{chip.emoji}</span>
              <span className="shop-nav-chip-label">{chip.label}</span>
              {chip.count != null ? <span className="shop-nav-chip-count">{chip.count}</span> : null}
            </button>
          ))}
        </div>
      </div>

      {showPagination ? (
        <div className="shop-nav-section">
          <div className="shop-nav-pagination" aria-label="Страницы каталога">
            <div className="shop-nav-pagination-main" role="toolbar" aria-label="Перелистывание страниц">
              <button
                type="button"
                className="shop-nav-page-btn shop-nav-page-btn-edge"
                disabled={disabled || page <= 0}
                aria-label="Первая страница"
                onClick={() => onGoToPage(0)}
              >
                <ChevronIcon direction="left" double />
              </button>
              <button
                type="button"
                className="shop-nav-page-btn"
                disabled={disabled || page <= 0}
                aria-label="Предыдущая страница"
                onClick={() => onGoToPage(page - 1)}
              >
                <ChevronIcon direction="left" />
              </button>

              <label className="shop-nav-page-jump">
                <span className="shop-nav-page-jump-label">Стр.</span>
                <input
                  type="text"
                  inputMode="numeric"
                  className="shop-nav-page-input"
                  value={pageText}
                  disabled={disabled}
                  aria-label={`Страница от 1 до ${totalPages}`}
                  onChange={handlePageInput}
                  onBlur={applyPageJump}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      applyPageJump()
                    }
                  }}
                />
                <span className="shop-nav-page-jump-total">из {totalPages}</span>
              </label>

              <button
                type="button"
                className="shop-nav-page-btn"
                disabled={disabled || page >= totalPages - 1}
                aria-label="Следующая страница"
                onClick={() => onGoToPage(page + 1)}
              >
                <ChevronIcon direction="right" />
              </button>
              <button
                type="button"
                className="shop-nav-page-btn shop-nav-page-btn-edge"
                disabled={disabled || page >= totalPages - 1}
                aria-label="Последняя страница"
                onClick={() => onGoToPage(totalPages - 1)}
              >
                <ChevronIcon direction="right" double />
              </button>
            </div>

            <p className="shop-nav-page-total">всего {totalItems}</p>
          </div>
        </div>
      ) : null}
    </nav>
  )
}

export { pickEmptyMessage }
