export default function ShopSkeletonGrid({ count = 8, gridClassName = 'shop-shelf-grid-cols-2' }) {
  return (
    <div className={`shop-shelf-grid ${gridClassName}`} aria-hidden>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="shop-shelf-skeleton">
          <div className="shop-skeleton-surface" />
          <div className="shop-skeleton-body">
            <div className="shop-skeleton-emoji" />
            <div className="shop-skeleton-line shop-skeleton-line-lg" />
            <div className="shop-skeleton-line shop-skeleton-line-sm" />
            <div className="shop-skeleton-meta">
              <div className="shop-skeleton-line shop-skeleton-line-xs" />
              <div className="shop-skeleton-line shop-skeleton-line-xs" />
            </div>
          </div>
          <div className="shop-skeleton-btn" />
        </div>
      ))}
    </div>
  )
}
