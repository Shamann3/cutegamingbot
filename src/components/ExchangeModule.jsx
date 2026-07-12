import { useEffect, useMemo, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import FarmBackground from './FarmBackground'
import VineFrame from './VineFrame'
import ShopShelfGrid from './ShopShelfGrid'
import ShopNavigation, { pickEmptyMessage } from './ShopNavigation'
import ShopSearch from './ShopSearch'
import ShopSkeletonGrid from './ShopSkeletonGrid'
import ShopPurchaseModal from './ShopPurchaseModal'
import DonateModal from './DonateModal'
import ShopToolbar from './ShopToolbar'
import KutBalance from './KutBalance'
import TabAtmosphere from './TabAtmosphere'
import { useContextualDonate } from '../hooks/useContextualDonate'
import { useShop } from '../hooks/useShop'
import { useShopFavorites } from '../hooks/useShopFavorites'

function errorClass(code) {
  if (code === 'auth') return 'shop-exchange-toast-auth'
  if (code === 'rate_limit') return 'shop-exchange-toast-rate'
  if (code === 'maintenance') return 'shop-exchange-toast-maint'
  return 'shop-exchange-toast-error'
}

export default function ExchangeModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
}) {
  const { playSound } = useSettings()
  const { isFavorite, toggleFavorite } = useShopFavorites()
  const {
    kut,
    couponCount,
    sortFilters,
    activeCategory,
    search,
    setSearch,
    priceFilter,
    sortBy,
    sortOrder,
    items,
    page,
    totalPages,
    totalItems,
    initialLoading,
    refreshing,
    error,
    errorCode,
    buyingItemId,
    purchaseMessage,
    pageSize,
    gridClassName,
    selectSort,
    resetSort,
    goToPage,
    changePriceFilter,
    changeSort,
    buyItem,
  } = useShop({ isActive })

  const [selectedItem, setSelectedItem] = useState(null)
  const [pendingGuide, setPendingGuide] = useState(null)
  const [highlightItemId, setHighlightItemId] = useState(null)

  useEffect(() => {
    if (!isActive) return
    if (!initialSearch && !initialItemId) return
    if (initialSearch) setSearch(initialSearch)
    setPendingGuide({
      itemId: initialItemId ? String(initialItemId) : '',
      highlightOnly: initialHighlightOnly,
    })
  }, [initialSearch, initialItemId, initialHighlightOnly, isActive, setSearch])

  useEffect(() => {
    if (!pendingGuide || initialLoading) return
    if (pendingGuide.itemId) {
      const found = items.find((item) => String(item.id) === pendingGuide.itemId)
      if (found) {
        if (pendingGuide.highlightOnly) {
          setHighlightItemId(pendingGuide.itemId)
          requestAnimationFrame(() => {
            document.getElementById(`shop-guide-tile-${found.id}`)?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
            })
          })
        } else {
          setSelectedItem(found)
        }
      }
    }
    setPendingGuide(null)
    onSearchUsed?.()
  }, [pendingGuide, initialLoading, items, onSearchUsed])

  useEffect(() => {
    if (!highlightItemId) return undefined
    const timer = setTimeout(() => setHighlightItemId(null), 10000)
    return () => clearTimeout(timer)
  }, [highlightItemId])

  const {
    donateOpen,
    donateContext,
    openDonate,
    openContextualDonate,
    closeDonate,
  } = useContextualDonate()

  const displayItems = useMemo(() => {
    const favs = items.filter((item) => isFavorite(item.id))
    const regular = items.filter((item) => !isFavorite(item.id))
    return [...favs, ...regular]
  }, [items, isFavorite])

  const emptyCatalog = !initialLoading && items.length === 0
  const catalogBusy = refreshing || Boolean(buyingItemId)

  const handleConfirmBuy = async (itemId, quantity, useCoupon) => {
    try {
      await buyItem(itemId, quantity, useCoupon)
      playSound('harvest')
      setSelectedItem(null)
    } catch {
      // ошибка в баннере
    }
  }

  return (
    <div className="relative min-h-screen tab-theme-shop shop-exchange">
      <FarmBackground />
      <TabAtmosphere variant="shop" />

      <div className="relative z-10 shop-exchange-shell py-4 pb-2 animate-slide-up">
        <header className="shop-exchange-header">
          <div className="shop-exchange-header-main">
            <div>
              <p className="shop-exchange-eyebrow">Cute</p>
              <h1 className="shop-exchange-title">Магазин</h1>
            </div>
          </div>
          <KutBalance
            value={kut}
            className="shop-exchange-balance"
            onDonate={openDonate}
          />
        </header>

        <ShopSearch
          value={search}
          onChange={setSearch}
          disabled={catalogBusy && !search}
        />

        <ShopToolbar
          priceFilter={priceFilter}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onPriceFilterChange={changePriceFilter}
          onSortChange={changeSort}
          disabled={catalogBusy}
        />

        {purchaseMessage ? (
          <p className="shop-exchange-toast shop-exchange-toast-ok" role="status">
            {purchaseMessage}
          </p>
        ) : null}

        {error ? (
          <p className={`shop-exchange-toast ${errorClass(errorCode)}`} role="alert">
            {error}
          </p>
        ) : null}

        <VineFrame className="shop-exchange-frame">
          <section className="shop-exchange-panel" aria-label="Магазин">
            <div
              id="onboarding-shop-showroom"
              className={`shop-exchange-showroom ${refreshing ? 'shop-exchange-showroom-refresh' : ''}`}
            >
              {initialLoading ? (
                <ShopSkeletonGrid count={pageSize} gridClassName={gridClassName} />
              ) : emptyCatalog ? (
                <p className="shop-exchange-empty">{pickEmptyMessage(activeCategory)}</p>
              ) : (
                <ShopShelfGrid
                  items={displayItems}
                  kut={kut}
                  gridClassName={gridClassName}
                  highlightItemId={highlightItemId}
                  onSelect={setSelectedItem}
                  buyingItemId={buyingItemId}
                  disabled={catalogBusy}
                  isFavorite={isFavorite}
                  onToggleFavorite={toggleFavorite}
                />
              )}
            </div>

            <ShopNavigation
              sortFilters={sortFilters}
              activeCategory={activeCategory}
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              disabled={catalogBusy}
              onSelectSort={selectSort}
              onResetSort={resetSort}
              onGoToPage={goToPage}
            />
          </section>
        </VineFrame>
      </div>

      <ShopPurchaseModal
        item={selectedItem}
        kut={kut}
        couponCount={couponCount}
        isOpen={Boolean(selectedItem)}
        isBuying={buyingItemId === selectedItem?.id}
        onClose={() => setSelectedItem(null)}
        onConfirm={handleConfirmBuy}
        onContextualDonate={(payload) => {
          openContextualDonate(payload)
          setSelectedItem(null)
        }}
      />

      <DonateModal
        isOpen={donateOpen}
        onClose={closeDonate}
        context={donateContext}
      />
    </div>
  )
}
