import { apiRequest } from './apiClient'

export function fetchPlayerProfile(userId) {
  return apiRequest(`/api/profile/${Number(userId)}`)
}

export function fetchMyProfile() {
  return apiRequest('/api/me')
}

export function telegramProfileUrl(username) {
  const handle = String(username || '').trim().replace(/^@/, '')
  if (!handle) return null
  return `https://t.me/${handle}`
}
