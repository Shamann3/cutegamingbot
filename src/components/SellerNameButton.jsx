export default function SellerNameButton({
  sellerId,
  sellerLabel,
  sellerName,
  className = '',
  onOpenProfile,
  stopPropagation = false,
}) {
  const label = sellerName || sellerLabel || 'Игрок'
  const canOpen = Boolean(sellerId && onOpenProfile)

  if (!canOpen) {
    return <span className={className}>{label}</span>
  }

  const handleClick = (event) => {
    if (stopPropagation) event.stopPropagation()
    event.preventDefault()
    onOpenProfile(sellerId)
  }

  return (
    <button
      type="button"
      className={`market-seller-link ${className}`.trim()}
      onClick={handleClick}
      aria-label={`Профиль продавца ${label}`}
    >
      {label}
    </button>
  )
}
