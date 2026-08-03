import { useOpenPlayerProfile } from '../context/PlayerProfileContext'

export default function SellerNameButton({
  sellerId,
  sellerLabel,
  sellerName,
  className = '',
  onOpenProfile,
  stopPropagation = false,
}) {
  const openFromContext = useOpenPlayerProfile()
  const openProfile = onOpenProfile || openFromContext
  const label = sellerName || sellerLabel || 'Игрок'
  const canOpen = Boolean(sellerId && openProfile)

  if (!canOpen) {
    return <span className={className}>{label}</span>
  }

  const handleClick = (event) => {
    if (stopPropagation) event.stopPropagation()
    event.preventDefault()
    openProfile(sellerId)
  }

  return (
    <button
      type="button"
      className={`market-seller-link user-name-link ${className}`.trim()}
      onClick={handleClick}
      aria-label={`Профиль продавца ${label}`}
    >
      {label}
    </button>
  )
}
