/**
 * Сегмент-переключатель с плавающей «водяной» таблеткой.
 */
export default function SegmentTabs({
  items,
  value,
  onChange,
  ariaLabel = 'Разделы',
  className = '',
}) {
  const index = Math.max(0, items.findIndex((item) => item.id === value))

  return (
    <div
      className={`segment-tabs ${className}`.trim()}
      role="tablist"
      aria-label={ariaLabel}
      style={{
        '--seg-count': items.length,
        '--seg-index': index,
      }}
    >
      <span className="segment-tabs-pill" aria-hidden />
      {items.map((item) => {
        const selected = item.id === value
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={`segment-tab${selected ? ' segment-tab-active' : ''}`}
            onClick={() => onChange?.(item.id)}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
