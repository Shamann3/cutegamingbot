import { apiRequest } from './apiClient'

export function fetchGiveaways() {
  return apiRequest('/api/giveaways')
}

export function fetchGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}`)
}

export function participateInGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}/participate`, {
    method: 'POST',
    body: {},
  })
}
