import { useOpenPlayerProfile } from '../context/PlayerProfileContext'

/**
 * Кликабельное имя пользователя → модалка профиля.
 * Использовать везде, где упоминается игрок.
 */
export default function UserNameLink({
  userId,
  name,
  className = '',
  stopPropagation = false,
  children,
}) {
  const openProfile = useOpenPlayerProfile()
  const label = children ?? name ?? 'Игрок'
  const canOpen = Boolean(userId && openProfile)

  if (!canOpen) {
    return <span className={className}>{label}</span>
  }

  const handleClick = (event) => {
    if (stopPropagation) event.stopPropagation()
    event.preventDefault()
    openProfile(userId)
  }

  return (
    <button
      type="button"
      className={`user-name-link ${className}`.trim()}
      onClick={handleClick}
      aria-label={`Профиль игрока ${typeof label === 'string' ? label : name || ''}`}
    >
      {label}
    </button>
  )
}
