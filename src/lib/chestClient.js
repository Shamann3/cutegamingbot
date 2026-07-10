import { apiRequest } from './apiClient'

export function fetchChestState() {
  return apiRequest('/api/chests/state')
}

export function openChests(count) {
  return apiRequest('/api/chests/open', { method: 'POST', body: { count } })
}

export function fetchCollection() {
  return apiRequest('/api/chests/collection')
}

export function buyCosmetic(cosmeticId) {
  return apiRequest('/api/chests/buy', { method: 'POST', body: { cosmeticId } })
}

export function equipCosmetic(cosmeticId, equipped) {
  return apiRequest('/api/chests/equip', { method: 'POST', body: { cosmeticId, equipped } })
}

export function fetchDropFeed() {
  return apiRequest('/api/chests/feed')
}

export function fetchEquipped() {
  return apiRequest('/api/cosmetics/equipped')
}
