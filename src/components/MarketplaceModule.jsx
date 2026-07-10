import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import FarmBackground from './FarmBackground'
import VineFrame from './VineFrame'
import ShopNavigation from './ShopNavigation'
import ShopSearch from './ShopSearch'
import ShopSkeletonGrid from './ShopSkeletonGrid'
import ShopToolbar from './ShopToolbar'
import KutBalance from './KutBalance'
import DonateModal from './DonateModal'
import MarketShelfTile from './MarketShelfTile'
import MarketListingModal from './MarketListingModal'
import MarketSellModal from './MarketSellModal'
import PlayerProfileModal from './PlayerProfileModal'
import { useMarketplace } from '../hooks/useMarketplace'
import { useContextualDonate } from '../hooks/useContextualDonate'
import TabAtmosphere from './TabAtmosphere'

function errorClass(code) {
  if (code === 'auth') return 'market-toast-auth'
  if (code === 'rate_limit') return 'market-toast-rate'
  if (code === 'maintenance') return 'market-toast-maint'
  return 'market-toast-error'
}

function marketEmptyMessage(categoryId, hasSearch) {
  if (hasSearch) return 'Лотов по запросу не найдено. Попробуйте другое название'
  if (categoryId && categoryId !== 'all') {
    return 'В этой категории пока нет лотов от игроков'
  }
  return 'Биржа пуста. Выставьте свой предмет и станьте первым продавцом'
}

export default function MarketplaceModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
}) {
  const { playSound } = useSettings()
  const {
    kut,
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
    busyListingId,
    actionMessage,
    sellableItems,
    sellableLoading,
    sellableError,
    commissionPercent,
    pageSize,
    gridClassName,
    selectSort,
    resetSort,
    goToPage,
    changePriceFilter,
    changeSort,
    buyListing,
    cancelListing,
    createListing,
    loadSellable,
  } = useMarketplace({ isActive })

  const [selectedItem, setSelectedItem] = useState(null)
  const [pendingGuide, setPendingGuide] = useState(null)
  const [highlightItemId, setHighlightItemId] = useState(null)
  const [sellOpen, setSellOpen] = useState(false)
  const {
    donateOpen,
    donateContext,
    openDonate,
    openContextualDonate,
    closeDonate,
  } = useContextualDonate()
  const [listingBusy, setListingBusy] = useState(false)
  const [profileUserId, setProfileUserId] = useState(null)

  const emptyCatalog = !initialLoading && items.length === 0
  const catalogBusy = refreshing || Boolean(busyListingId) || listingBusy
  const hasSearch = Boolean(search.trim())

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
      const found = items.find((item) => String(item.itemId) === pendingGuide.itemId)
      if (found) {
        if (pendingGuide.highlightOnly) {
          setHighlightItemId(pendingGuide.itemId)
          requestAnimationFrame(() => {
            document.getElementById(`market-guide-tile-${found.id}`)?.scrollIntoView({
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

  const openSell = async () => {
    setSellOpen(true)
    try {
      await loadSellable()
    } catch {
      // error state set in loadSellable, shown in modal
    }
  }

  const handleBuy = async (listingId, quantity) => {
    try {
      const result = await buyListing(listingId, quantity)
      if (!result) return
      playSound('harvest')
      setSelectedItem(null)
    } catch {
      // error banner
    }
  }

  const handleCancel = async (listingId) => {
    try {
      const result = await cancelListing(listingId)
      if (!result) return
      setSelectedItem(null)
    } catch {
      // error banner
    }
  }

  const handleSell = async (itemId, price, quantity) => {
    setListingBusy(true)
    try {
      await createListing(itemId, price, quantity)
      playSound('plant')
      setSellOpen(false)
    } catch {
      // error banner
    } finally {
      setListingBusy(false)
    }
  }

  return (
    <div className="relative min-h-screen tab-theme-market market-exchange">
      <FarmBackground />
      <TabAtmosphere variant="market" />

      <div className="relative z-10 market-shell py-4 pb-2 animate-slide-up">
        <header className="market-hero">
          <div className="market-hero-copy">
            <p className="market-hero-eyebrow">Игроки · торговля</p>
            <h1 className="market-hero-title">Биржа</h1>
          </div>
          <KutBalance
            value={kut}
            className="market-hero-balance"
            onDonate={openDonate}
          />
        </header>

        <section className="market-sell-card" aria-label="Выставить предмет">
          <div className="market-sell-card-glow" aria-hidden />
          <div className="market-sell-card-content">
            <span className="market-sell-card-icon" aria-hidden>📤</span>
            <div className="market-sell-card-text">
              <p className="market-sell-card-title">Продать из рюкзака</p>
              <p className="market-sell-card-sub">Комиссия {commissionPercent}% при продаже · саженцы и вода запрещены</p>
            </div>
          </div>
          <button
            type="button"
            className="market-sell-card-btn"
            disabled={catalogBusy}
            onClick={openSell}
          >
            Выставить лот
          </button>
        </section>

        <div className="market-tools-row">
          <ShopSearch
            className="market-search"
            value={search}
            onChange={setSearch}
            disabled={catalogBusy && !search}
            placeholder="Искать лоты игроков…"
            ariaLabel="Поиск лотов на бирже"
          />
          <ShopToolbar
            className="market-toolbar"
            priceFilter={priceFilter}
            sortBy={sortBy}
            sortOrder={sortOrder}
            onPriceFilterChange={changePriceFilter}
            onSortChange={changeSort}
            disabled={catalogBusy}
          />
        </div>

        {!initialLoading && totalItems > 0 ? (
          <p className="market-lots-badge" role="status">
            <span className="market-lots-badge-dot" aria-hidden />
            {totalItems} {totalItems === 1 ? 'лот' : totalItems < 5 ? 'лота' : 'лотов'} на бирже
          </p>
        ) : null}

        {actionMessage ? (
          <p className="market-toast market-toast-ok" role="status">
            {actionMessage}
          </p>
        ) : null}

        {error ? (
          <p className={`market-toast ${errorClass(errorCode)}`} role="alert">
            {error}
          </p>
        ) : null}

        <VineFrame className="market-board-frame">
          <section id="onboarding-market-board" className="market-board" aria-label="Лоты игроков">
            <div className={`market-board-showroom ${refreshing ? 'market-board-showroom-refresh' : ''}`}>
              {initialLoading ? (
                <ShopSkeletonGrid count={pageSize} gridClassName={gridClassName} />
              ) : emptyCatalog ? (
                <div className="market-board-empty">
                  <span className="market-board-empty-icon" aria-hidden>💱</span>
                  <p>{marketEmptyMessage(activeCategory, hasSearch)}</p>
                </div>
              ) : (
                <div className={`market-shelf-grid ${gridClassName}`}>
                  {items.map((item) => (
                    <MarketShelfTile
                      key={item.id}
                      item={item}
                      kut={kut}
                      onSelect={setSelectedItem}
                      onOpenSellerProfile={setProfileUserId}
                      isBusy={busyListingId === item.id}
                      disabled={catalogBusy && busyListingId !== item.id}
                      isHighlighted={highlightItemId != null && String(highlightItemId) === String(item.itemId)}
                    />
                  ))}
                </div>
              )}
            </div>

            <ShopNavigation
              className="market-nav"
              sortFilters={sortFilters}
              activeCategory={activeCategory}
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              disabled={catalogBusy}
              onSelectSort={selectSort}
              onResetSort={resetSort}
              onGoToPage={goToPage}
              ariaLabel="Навигация по лотам"
              categoriesLabel="Тип предмета"
              allChipEmoji="💱"
            />
          </section>
        </VineFrame>
      </div>

      <MarketListingModal
        item={selectedItem}
        kut={kut}
        isOpen={Boolean(selectedItem)}
        isBusy={busyListingId === selectedItem?.id}
        commissionPercent={commissionPercent}
        onClose={() => setSelectedItem(null)}
        onConfirmBuy={handleBuy}
        onCancelListing={handleCancel}
        onOpenSellerProfile={setProfileUserId}
        onContextualDonate={(payload) => {
          openContextualDonate(payload)
          setSelectedItem(null)
        }}
      />

      <PlayerProfileModal
        userId={profileUserId}
        isOpen={Boolean(profileUserId)}
        onClose={() => setProfileUserId(null)}
      />

      <MarketSellModal
        items={sellableItems}
        isOpen={sellOpen}
        isLoading={sellableLoading}
        isBusy={listingBusy}
        error={sellableError}
        commissionPercent={commissionPercent}
        onClose={() => setSellOpen(false)}
        onConfirm={handleSell}
        onRetry={() => loadSellable().catch(() => {})}
      />

      <DonateModal
        isOpen={donateOpen}
        onClose={closeDonate}
        context={donateContext}
      />
    </div>
  )
}
