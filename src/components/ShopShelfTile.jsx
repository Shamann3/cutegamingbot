import { formatKut } from '../utils/formatKut'
import { itemBuyPrice } from '../lib/shopClient'
import { useSettings } from '../context/SettingsContext'
import { PERF_MODES } from '../constants/performance'
import { useShopEmojiPop } from '../hooks/useShopEmojiPop'

export default function ShopShelfTile({
  item,
  kut,
  onSelect,
  isBuying = false,
  disabled = false,
  isFavorite = false,
  onToggleFavorite,
  isHighlighted = false,
}) {
  const hasSale = item.salePrice != null && item.salePrice > 0
  const price = itemBuyPrice(item)
  const canAfford = kut == null || kut >= price
  const outOfStock = item.remains < 1
  const tileDisabled = disabled || isBuying || outOfStock
  const { performanceMode } = useSettings()
  const emojiPopping = useShopEmojiPop(item.id, performanceMode === PERF_MODES.FULL)

  return (
    <article
      id={`shop-guide-tile-${item.id}`}
      className={`shop-shelf-tile ${hasSale ? 'shop-shelf-tile-sale' : ''} ${!canAfford || outOfStock ? 'shop-shelf-tile-muted' : ''} ${isBuying ? 'shop-shelf-tile-busy' : ''} ${isFavorite ? 'shop-shelf-tile-fav' : ''} ${isHighlighted ? 'shop-shelf-tile-guide' : ''}`}
    >
      <div className="shop-shelf-surface" aria-hidden />
      <button
        type="button"
        className="shop-shelf-fav-btn"
        aria-label={isFavorite ? 'Убрать из избранного' : 'В избранное'}
        onClick={(event) => {
          event.stopPropagation()
          onToggleFavorite?.(item.id)
        }}
      >
        {isFavorite ? '★' : '☆'}
      </button>
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
        <div className="shop-shelf-meta">
          <span className="shop-shelf-stock">{formatKut(item.remains)}</span>
          <div className="shop-shelf-price">
            {hasSale ? (
              <span className="shop-shelf-price-stack">
                <span className="shop-shelf-price-old">{formatKut(item.price)}</span>
                <span className="shop-shelf-price-main">{formatKut(price)}</span>
              </span>
            ) : (
              <span className="shop-shelf-price-single">{formatKut(price)}</span>
            )}
          </div>
        </div>
        <div className="shop-shelf-buy-hint">
          {isBuying ? '…' : outOfStock ? 'Нет' : !canAfford ? 'Недостаточно кут' : 'КУПИТЬ'}
        </div>
      </button>
    </article>
  )
}
