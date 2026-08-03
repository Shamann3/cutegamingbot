import { apiRequest } from './apiClient'

export function fetchPlayerProfile(userId) {
  return apiRequest(`/api/profile/${Number(userId)}`)
}

export function fetchMyProfile() {
  return apiRequest('/api/me')
}

export function telegramProfileUrl(username, userId) {
  const handle = String(username || '').trim().replace(/^@/, '')
  if (handle) return `https://t.me/${handle}`
  const id = Number(userId)
  if (Number.isFinite(id) && id > 0) return `tg://user?id=${id}`
  return null
}
