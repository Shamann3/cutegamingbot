import { getAdminDisplayName } from './displayName'
import { getTelegramUser } from './telegram'

export function getAdminProfile() {
  const user = getTelegramUser()
  const displayName = getAdminDisplayName()

  return {
    displayName,
    username: user?.username || null,
    photoUrl: user?.photo_url || null,
    userId: user?.id || null,
  }
}

export function getAdminInitials(name) {
  const trimmed = (name || 'A').trim()
  if (!trimmed) return 'A'
  return trimmed.charAt(0).toUpperCase()
}
