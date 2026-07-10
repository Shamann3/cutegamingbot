import ShopShelfTile from './ShopShelfTile'

export default function ShopShelfGrid({
  items,
  kut,
  onSelect,
  buyingItemId,
  disabled,
  isFavorite,
  onToggleFavorite,
  highlightItemId = null,
  gridClassName = 'shop-shelf-grid-cols-2',
}) {
  return (
    <div
      className={`shop-shelf-grid ${gridClassName}`}
      role="list"
      aria-label="Товары на прилавке"
    >
      {items.map((item) => (
        <ShopShelfTile
          key={item.id}
          item={item}
          kut={kut}
          onSelect={onSelect}
          isBuying={buyingItemId === item.id}
          disabled={disabled && buyingItemId !== item.id}
          isFavorite={isFavorite?.(item.id)}
          onToggleFavorite={onToggleFavorite}
          isHighlighted={highlightItemId != null && String(highlightItemId) === String(item.id)}
        />
      ))}
    </div>
  )
}
