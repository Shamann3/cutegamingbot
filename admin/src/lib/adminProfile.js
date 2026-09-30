import { getAdminDisplayName } from './displayName'
import { getTelegramUser } from './telegram'

let standIn = null

/** Копия панели «от лица» человека: меню и приветствие показывают его, а не создателя. */
export function setProfileStandIn(person) {
  const name = String(person?.displayName || '').trim()
  standIn = name
    ? { displayName: name, username: person.username || null, photoUrl: null, userId: person.userId ?? null }
    : null
}

export function getAdminProfile() {
  if (standIn) return { ...standIn }
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
