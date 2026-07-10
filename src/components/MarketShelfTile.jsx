import { formatKut } from '../utils/formatKut'
import { listingUnitPrice } from '../lib/marketClient'
import { useSettings } from '../context/SettingsContext'
import { PERF_MODES } from '../constants/performance'
import { useShopEmojiPop } from '../hooks/useShopEmojiPop'
import SellerNameButton from './SellerNameButton'

export default function MarketShelfTile({
  item,
  kut,
  onSelect,
  onOpenSellerProfile,
  isBusy = false,
  disabled = false,
  isHighlighted = false,
}) {
  const price = listingUnitPrice(item)
  const canAfford = kut >= price
  const outOfStock = item.quantity < 1
  const tileDisabled = disabled || isBusy || outOfStock
  const { performanceMode } = useSettings()
  const emojiPopping = useShopEmojiPop(item.id, performanceMode === PERF_MODES.FULL)

  return (
    <article
      id={`market-guide-tile-${item.id}`}
      className={`shop-shelf-tile market-shelf-tile ${!canAfford || outOfStock ? 'shop-shelf-tile-muted' : ''} ${isBusy ? 'shop-shelf-tile-busy' : ''} ${item.isMine ? 'market-shelf-tile-mine' : ''} ${isHighlighted ? 'shop-shelf-tile-guide' : ''}`}
    >
      <div className="shop-shelf-surface" aria-hidden />
      {item.isMine ? (
        <span className="market-shelf-mine-badge" aria-hidden>Мой</span>
      ) : null}
      <button
        type="button"
        className="shop-shelf-product-btn"
        disabled={tileDisabled}
        onClick={() => onSelect(item)}
        aria-label={`Открыть ${item.name}`}
      >
        <span
          className={`shop-shelf-emoji ${emojiPopping ? 'shop-shelf-emoji--pop' : ''}`}
          aria-hidden
        >
          {item.emoji}
        </span>
        <p className="shop-shelf-name" title={item.name}>{item.name}</p>
        <SellerNameButton
          className="market-shelf-seller"
          sellerId={item.sellerId}
          sellerLabel={item.sellerLabel}
          sellerName={item.sellerName}
          onOpenProfile={onOpenSellerProfile}
          stopPropagation
        />
        <div className="shop-shelf-meta">
          <span className="shop-shelf-stock">{formatKut(item.quantity)} шт</span>
          <div className="shop-shelf-price">
            <span className="shop-shelf-price-single">{formatKut(price)}</span>
          </div>
        </div>
        <div className="shop-shelf-buy-hint market-shelf-hint">
          {isBusy ? '…' : outOfStock ? 'Нет' : !canAfford ? 'Мало кут' : 'СМОТРЕТЬ'}
        </div>
      </button>
    </article>
  )
}
